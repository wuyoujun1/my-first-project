#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
极速音频输入 - 一口气发送 + 耗时统计
"""
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

FRAME_SIZE = 1280

def b64decode(s): return base64.b64decode(s).decode() if s else ""

def auth_url():
    gmt = time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime())
    sig_origin = f"host: {HOST}\ndate: {gmt}\nGET {URI} HTTP/1.1"
    sig = base64.b64encode(hmac.new(APISECRET.encode(), sig_origin.encode(), hashlib.sha256).digest()).decode()
    auth_origin = f'api_key="{APIKEY}", algorithm="hmac-sha256", headers="host date request-line", signature="{sig}"'
    authorization = base64.b64encode(auth_origin.encode()).decode()
    return f"wss://{HOST}{URI}?authorization={authorization}&date={urllib.parse.quote(gmt)}&host={HOST}"

def build_pkg(audio_b64: str, status: int):
    return json.dumps({
        "header": {
            "appid": APPID,
            "sn": "jetson001",
            "status": status,
            "stmid": "audio-1",
            "scene": "main",
            "interact_mode": "oneshot"
        },
        "parameter": {
            "nlp": {"nlp": {"encoding": "utf8", "compress": "raw", "format": "json"}},
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
            "audio": {
                "encoding": "raw",
                "sample_rate": 16000,
                "channels": 1,
                "bit_depth": 16,
                "status": status,
                "audio": audio_b64
            }
        }
    }, ensure_ascii=False)

def run(audio_file: str):
    if not os.path.exists(audio_file):
        print(f"❌ 找不到音频文件: {audio_file}")
        return
    
    with open(audio_file, 'rb') as f:
        audio_data = f.read()
    
    frames = [base64.b64encode(audio_data[i:i+FRAME_SIZE]).decode() 
              for i in range(0, len(audio_data), FRAME_SIZE)]
    
    print(f"【音频】{audio_file}, {len(audio_data)} bytes, 共 {len(frames)} 帧")
    
    # 计时器
    timer = {
        "start": time.time(),
        "connected": 0,
        "first_sent": 0,
        "last_sent": 0,
        "first_result": 0,
        "done": 0
    }
    
    nlp_frames = []
    tts_chunks = []
    first_result_received = [False]
    
    def on_open(ws):
        timer["connected"] = time.time()
        
        # 一口气发送所有帧（无间隔）
        for i, frame_data in enumerate(frames):
            status = 0 if i == 0 else (2 if i == len(frames)-1 else 1)
            pkg = build_pkg(frame_data, status)
            ws.send(pkg)
            
            if i == 0:
                timer["first_sent"] = time.time()
            elif i == len(frames)-1:
                timer["last_sent"] = time.time()
                print(f"【发送】全部 {len(frames)} 帧已发出，耗时 {(timer['last_sent']-timer['first_sent'])*1000:.1f}ms")
        
    def on_message(ws, message):
        resp = json.loads(message)
        hdr = resp.get("header", {})
        
        if hdr.get("code", 0) != 0:
            print(f"🚨 错误: {hdr.get('message')}")
            ws.close()
            return
        
        # 记录收到首条结果的时间
        if not first_result_received[0]:
            first_result_received[0] = True
            timer["first_result"] = time.time()
        
        # 收集结果
        if "nlp" in resp.get("payload", {}):
            nlp_frames.append(resp["payload"]["nlp"])
        
        if "tts" in resp.get("payload", {}):
            tts_chunks.append(resp["payload"]["tts"])
        
        # 结束处理
        if hdr.get("status") == 2:
            timer["done"] = time.time()
            
            # 输出结果
            if nlp_frames:
                full_nlp = "".join(b64decode(f.get("text", "")) for f in sorted(nlp_frames, key=lambda x: x.get("seq", 0)))
                print(f"【回答】{full_nlp[:50]}..." if len(full_nlp) > 50 else f"【回答】{full_nlp}")
            
            if tts_chunks:
                sorted_chunks = sorted(tts_chunks, key=lambda x: x["seq"])
                mp3_data = b"".join(base64.b64decode(c["audio"]) for c in sorted_chunks)
                if len(mp3_data) > 0:
                    with open("reply.mp3", "wb") as f:
                        f.write(mp3_data)
            
            # 耗时统计
            total = timer["done"] - timer["start"]
            connect_time = (timer["connected"] - timer["start"]) * 1000
            send_time = (timer["last_sent"] - timer["first_sent"]) * 1000 if timer["last_sent"] else 0
            wait_time = (timer["first_result"] - timer["last_sent"]) * 1000 if timer["first_result"] and timer["last_sent"] else 0
            process_time = (timer["done"] - timer["first_result"]) * 1000 if timer["done"] and timer["first_result"] else 0
            
            print(f"\n⏱️  耗时统计:")
            print(f"   总耗时:     {total*1000:.1f}ms ({total:.2f}s)")
            print(f"   - 建立连接: {connect_time:.1f}ms")
            print(f"   - 发送音频: {send_time:.1f}ms ({len(frames)}帧)")
            print(f"   - 等待首响: {wait_time:.1f}ms")
            print(f"   - 结果传输: {process_time:.1f}ms")
            print(f"   音频大小:   {len(mp3_data)/1024:.1f}KB" if tts_chunks else "")
            
            ws.close()
    
    ws = websocket.WebSocketApp(
        auth_url(),
        on_open=on_open,
        on_message=on_message
    )
    ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})

if __name__ == "__main__":
    run("input.pcm")  # 如果不是input.pcm请改成你的文件名