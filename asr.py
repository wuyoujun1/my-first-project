import json
import base64
import time
import hashlib
import hmac
import websocket
import ssl
import urllib.parse
import os

APPID = "8e738b41"
APIKEY = "a97ad5f0578fbc3808e1afa7f8fb7446"
APISECRET = "M2QwMWFjNGI3NTQxMjc5ZGNiNDVlNGQ0"
HOST = "aiui.xf-yun.com"
URI = "/v3/aiint/sos"

def b64decode(s): return base64.b64decode(s).decode() if s else ""

def auth_url():
    gmt = time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime())
    sig_origin = f"host: {HOST}\ndate: {gmt}\nGET {URI} HTTP/1.1"
    sig = base64.b64encode(hmac.new(APISECRET.encode(), sig_origin.encode(), hashlib.sha256).digest()).decode()
    auth_origin = f'api_key="{APIKEY}", algorithm="hmac-sha256", headers="host date request-line", signature="{sig}"'
    authorization = base64.b64encode(auth_origin.encode()).decode()
    return f"wss://{HOST}{URI}?authorization={authorization}&date={urllib.parse.quote(gmt)}&host={HOST}"

def build_pkg(text: str):
    return json.dumps({
        "header": {
            "appid": APPID,
            "sn": "jetson001",
            "status": 3,
            "stmid": "text-1",
            "scene": "main",
            "interact_mode": "oneshot"
        },
        "parameter": {
            "nlp": {"nlp": {"encoding": "utf8", "compress": "raw", "format": "json"}, "new_session": "false"},
            "tts": {
                "vcn": "x5_lingfeiyi_flow",
                "speed": 50, "volume": 50, "pitch": 50,
                "tts": {
                    "encoding": "lame",
                    "sample_rate": 16000, 
                    "channels": 1, 
                    "bit_depth": 16,
                    "frame_size": 0
                }
            }
        },
        "payload": {
            "text": {
                "encoding": "utf8", 
                "compress": "raw", 
                "format": "plain", 
                "status": 3,
                "text": base64.b64encode(text.encode()).decode()
            }
        }
    }, ensure_ascii=False)

def run(text: str):
    url = auth_url()
    iat_frames, nlp_frames, tts_chunks = [], [], []

    def _on_open(ws):
        ws.send(build_pkg(text))

    def _on_message(ws, message):
        resp = json.loads(message)
        hdr = resp.get("header", {})

        if "iat" in resp.get("payload", {}):
            iat_frames.append(resp["payload"]["iat"])

        if "nlp" in resp.get("payload", {}):
            nlp_frames.append(resp["payload"]["nlp"])

        if "tts" in resp.get("payload", {}):
            tts_chunks.append(resp["payload"]["tts"])

        if hdr.get("status") == 2:
            print("="*50)
            
            if iat_frames:
                full_iat = "".join(b64decode(f.get("text", "")) for f in sorted(iat_frames, key=lambda x: x.get("seq", 0)))
                print(f"【识别结果】{full_iat}")
            
            if nlp_frames:
                full_nlp = "".join(b64decode(f.get("text", "")) for f in sorted(nlp_frames, key=lambda x: x.get("seq", 0)))
                print(f"【大模型回答】{full_nlp}")
            
            if tts_chunks:
                sorted_chunks = sorted(tts_chunks, key=lambda x: x.get("seq", 0))
                mp3_data = b"".join(base64.b64decode(c.get("audio", "")) for c in sorted_chunks)
                
                if len(mp3_data) > 0:
                    filename = "reply.mp3"
                    with open(filename, "wb") as f:
                        f.write(mp3_data)
                    
                    file_size = len(mp3_data)
                    print(f"【音频生成】{filename} ({file_size} bytes / {file_size/1024:.2f} KB)")
                    
                    if os.name == 'nt':
                        try:
                            os.system(f"start {filename}")
                        except:
                            pass
                else:
                    print("【音频生成】⚠️ 音频数据为空")
            
            print("="*50)
            ws.close()

    ws = websocket.WebSocketApp(url, on_open=_on_open, on_message=_on_message)
    ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})

if __name__ == "__main__":
    run("一天有多少小时")
