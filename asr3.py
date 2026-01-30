import json
import base64
import time
import hashlib
import hmac
import websocket
import ssl
import urllib.parse
import threading
import queue
import sys
import os

try:
    import pygame
    pygame.mixer.init()
    HAS_AUDIO = True
    print("✅ 音频系统就绪")
except Exception as e:
    print(f"⚠️ 音频错误: {e}")
    HAS_AUDIO = False

try:
    import pyaudio
except ImportError:
    print("❌ 请先安装 PyAudio")
    sys.exit(1)

APPID = "8e738b41"
APIKEY = "a97ad5f0578fbc3808e1afa7f8fb7446"
APISECRET = "M2QwMWFjNGI3NTQxMjc5ZGNiNDVlNGQ0"
HOST = "aiui.xf-yun.com"
URI = "/v3/aiint/sos"

CHUNK = 1280
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

def auth_url():
    gmt = time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime())
    sig_origin = f"host: {HOST}\ndate: {gmt}\nGET {URI} HTTP/1.1"
    sig = base64.b64encode(hmac.new(APISECRET.encode(), sig_origin.encode(), hashlib.sha256).digest()).decode()
    auth_origin = f'api_key="{APIKEY}", algorithm="hmac-sha256", headers="host date request-line", signature="{sig}"'
    authorization = base64.b64encode(auth_origin.encode()).decode()
    return f"wss://{HOST}{URI}?authorization={authorization}&date={urllib.parse.quote(gmt)}&host={HOST}"

def get_pers_param():
    return json.dumps({"appid": APPID, "uid": "robot001"}, ensure_ascii=False)

def build_pkg(audio_b64, stmid, status):
    if status == 0:
        return json.dumps({
            "header": {
                "appid": APPID, "sn": "robot001", "status": 0,
                "stmid": stmid, "scene": "main",
                "interact_mode": "continuous",
                "pers_param": get_pers_param()
            },
            "parameter": {
                "iat": {"vgap": 60, "dwa": "wpgs", 
                       "iat": {"encoding": "utf8", "compress": "raw", "format": "json"}},
                "nlp": {"nlp": {"encoding": "utf8", "compress": "raw", "format": "json"},
                       "new_session": "false"},
                "tts": {"vcn": "x5_lingfeiyi_flow", "speed": 50, "volume": 50, "pitch": 50,
                       "tts": {"encoding": "lame", "sample_rate": 16000, "channels": 1, "bit_depth": 16}}
            },
            "payload": {
                "audio": {"encoding": "raw", "sample_rate": 16000, "channels": 1,
                         "bit_depth": 16, "status": 0, "audio": audio_b64}
            }
        }, ensure_ascii=False)
    else:
        return json.dumps({
            "header": {
                "appid": APPID, "sn": "robot001", "status": status,
                "stmid": stmid, "scene": "main",
                "interact_mode": "continuous",
                "pers_param": get_pers_param()
            },
            "payload": {
                "audio": {"encoding": "raw", "sample_rate": 16000, "channels": 1,
                         "bit_depth": 16, "status": status, "audio": audio_b64}
            }
        }, ensure_ascii=False)

class RobotASR:
    def __init__(self):
        self.audio_queue = queue.Queue()
        self.is_running = False
        self.ws = None
        self.stmid = f"robot-{int(time.time())}"
        
        # TTS控制
        self.tts_lock = threading.Lock()
        self.tts_buffer = []
        self.tts_counter = 0
        self.tts_timer = None
        
        self.current_text = ""
        self.is_speaking = False
        self.is_recording = True
        
        # 录音控制
        self.record_stream = None
        self.record_pa = None
        self.record_lock = threading.Lock()
        
    def start_recording(self):
        """启动录音"""
        with self.record_lock:
            if self.record_stream is None:
                try:
                    self.record_pa = pyaudio.PyAudio()
                    self.record_stream = self.record_pa.open(
                        format=FORMAT, channels=CHANNELS, rate=RATE,
                        input=True, frames_per_buffer=CHUNK
                    )
                    log("🎙️ 录音已启动")
                except Exception as e:
                    log(f"❌ 启动录音失败: {e}")

    def stop_recording(self):
        """停止录音"""
        with self.record_lock:
            if self.record_stream:
                try:
                    self.record_stream.stop_stream()
                    self.record_stream.close()
                except:
                    pass
                self.record_stream = None
            if self.record_pa:
                try:
                    self.record_pa.terminate()
                except:
                    pass
                self.record_pa = None
            log("🔇 录音已暂停")

    def record_forever(self):
        """录音线程 - 动态控制"""
        while self.is_running:
            # 如果应该录音但没有流，启动它
            if self.is_recording and self.record_stream is None:
                self.start_recording()
                time.sleep(0.1)  # 给一点时间初始化
                continue
            
            # 如果不应该录音但有流，关闭它
            if not self.is_recording and self.record_stream is not None:
                self.stop_recording()
                time.sleep(0.1)
                continue
            
            # 正常录音
            if self.is_recording and self.record_stream:
                try:
                    data = self.record_stream.read(CHUNK, exception_on_overflow=False)
                    
                    # AI说话时丢弃数据（静音）
                    if not self.is_speaking:
                        self.audio_queue.put(data)
                        
                except Exception as e:
                    log(f"录音错误: {e}")
                    # 出错时重置，下次循环会重新初始化
                    with self.record_lock:
                        self.record_stream = None
                        self.record_pa = None
                    time.sleep(0.5)
            else:
                time.sleep(0.05)
        
        # 清理
        self.stop_recording()

    def send_forever(self, ws):
        """持续发送"""
        is_first = True
        
        while self.is_running:
            try:
                data = self.audio_queue.get(timeout=1.0)
                audio_b64 = base64.b64encode(data).decode()
                
                if is_first:
                    pkg = build_pkg(audio_b64, self.stmid, 0)
                    is_first = False
                else:
                    pkg = build_pkg(audio_b64, self.stmid, 1)
                
                if ws.sock and ws.sock.connected:
                    ws.send(pkg)
                    
            except queue.Empty:
                continue
            except Exception as e:
                log(f"发送错误: {e}")
                time.sleep(0.5)

    def stop_speaking(self):
        """停止AI说话，恢复录音"""
        if self.is_speaking:
            try:
                pygame.mixer.music.stop()
            except:
                pass
            self.is_speaking = False
            with self.tts_lock:
                self.tts_buffer = []
            # 恢复录音
            self.is_recording = True

    def play_buffered_tts(self):
        """播放TTS（播放时暂停录音）"""
        with self.tts_lock:
            if not self.tts_buffer:
                return
            
            try:
                sorted_tts = sorted(self.tts_buffer, key=lambda x: x["seq"])
                mp3_data = b"".join([c["data"] for c in sorted_tts])
                self.tts_buffer = []
                
                if mp3_data:
                    self.tts_counter += 1
                    filename = f"reply_{self.tts_counter:03d}.mp3"
                    
                    with open(filename, "wb") as f:
                        f.write(mp3_data)
                    
                    if HAS_AUDIO:
                        # 暂停录音
                        self.is_recording = False
                        
                        pygame.mixer.music.stop()
                        self.is_speaking = True
                        
                        pygame.mixer.music.load(filename)
                        pygame.mixer.music.play()
                        log(f"🔊 播放语音 #{self.tts_counter} ({len(mp3_data)/1024:.1f} KB)")
                        
                        def wait_finish():
                            while pygame.mixer.music.get_busy() and self.is_speaking:
                                time.sleep(0.05)
                            
                            self.is_speaking = False
                            log("✅ 播放完成，恢复录音")
                            self.is_recording = True  # 这会触发录音线程重新初始化
                        
                        threading.Thread(target=wait_finish, daemon=True).start()
                    
            except Exception as e:
                log(f"播放错误: {e}")
                self.is_speaking = False
                self.is_recording = True

    def schedule_play(self):
        """延迟播放"""
        if self.tts_timer:
            self.tts_timer.cancel()
        
        self.tts_timer = threading.Timer(0.2, self.play_buffered_tts)
        self.tts_timer.start()

    def on_message(self, ws, message):
        try:
            resp = json.loads(message)
            hdr = resp.get("header", {})
            
            if hdr.get("code", 0) != 0:
                return
            
            payload = resp.get("payload", {})
            
            # 语音识别
            if "iat" in payload and not self.is_speaking:
                try:
                    iat_data = json.loads(base64.b64decode(payload["iat"]["text"]))
                    if "ws" in iat_data:
                        text = "".join([w["cw"][0]["w"] for w in iat_data["ws"] if w["cw"]])
                        if text and text != self.current_text:
                            self.current_text = text
                            if self.is_speaking:
                                self.stop_speaking()
                            print(f"\r👤 用户: {text}", end="", flush=True)
                            if iat_data.get("ls", False):
                                print()
                except:
                    pass
            
            # AI文字
            if "nlp" in payload and "text" in payload["nlp"]:
                try:
                    text = base64.b64decode(payload["nlp"]["text"]).decode('utf-8')
                    if text:
                        log(f"🤖 AI: {text}")
                except:
                    pass
            
            # TTS片段
            if "tts" in payload:
                try:
                    tts_data = payload["tts"]
                    seq = tts_data.get("seq", 0)
                    audio_b64 = tts_data.get("audio", "")
                    
                    if audio_b64:
                        audio_bytes = base64.b64decode(audio_b64)
                        if audio_bytes:
                            with self.tts_lock:
                                self.tts_buffer.append({"seq": seq, "data": audio_bytes})
                            
                            log(f"📦 片段 #{seq} ({len(audio_bytes)} bytes)")
                            self.schedule_play()
                            
                except Exception as e:
                    log(f"TTS错误: {e}")
            
            # 结束标记
            if hdr.get("status") == 2:
                log("✅ 收到结束标记")
                if self.tts_timer:
                    self.tts_timer.cancel()
                self.play_buffered_tts()
                
        except Exception as e:
            log(f"处理错误: {e}")

    def on_open(self, ws):
        log("✅ 已连接")
        self.is_running = True
        self.is_recording = True
        
        # 启动录音线程
        t1 = threading.Thread(target=self.record_forever)
        t1.daemon = True
        t1.start()
        
        # 启动发送线程
        t2 = threading.Thread(target=self.send_forever, args=(ws,))
        t2.daemon = True
        t2.start()
        
        log("🚀 就绪！直接说话")

    def on_close(self, ws, code, msg):
        log(f"🔌 连接关闭 (code: {code})")
        self.is_running = False
        self.is_recording = False

    def on_error(self, ws, error):
        log(f"⚠️ 错误: {error}")

    def run(self):
        log("🔌 启动中...")
        while True:
            try:
                self.ws = websocket.WebSocketApp(
                    auth_url(),
                    on_open=self.on_open,
                    on_message=self.on_message,
                    on_error=self.on_error,
                    on_close=self.on_close
                )
                self.ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})
                
                if self.is_running:
                    log("⚠️ 3秒后重连...")
                    time.sleep(3)
                else:
                    break
            except KeyboardInterrupt:
                log("👋 退出")
                self.is_running = False
                break

if __name__ == "__main__":
    print("="*60)
    print("机器狗语音系统 - 录音流修复版")
    print("="*60)
    
    try:
        robot = RobotASR()
        robot.run()
    except KeyboardInterrupt:
        print("\n已停止")