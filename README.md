# 🤖 机器狗语音对话系统

基于讯飞 AIUI 的实时语音交互系统，支持连续对话、自动播放、回声消除。

## 📁 文件说明

| 文件 | 功能 | 使用场景 |
|------|------|----------|
| `asr.py` | 文本交互 | 纯文字对话，无语音功能 |
| `asr1.py` | 单次语音对话 | 读取本地音频文件，一次性识别 |
| `asr2.py` | 录音工具 | 录制麦克风音频保存为 PCM 文件 |
| `asr3.py` | **连续语音对话** ⭐ | 实时对话，边说边识别，自动播放回答 |

## 🚀 快速开始

### 1. 环境配置

```bash
# 安装依赖
pip install websocket-client pyaudio pygame

# Windows 用户如果 PyAudio 安装失败，下载对应版本的 whl 安装
# https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio
# 例如 Python 3.11 64位：pip install PyAudio‑0.2.11‑cp311‑cp311‑win_amd64.whl
```

### 2. 创建讯飞 AIUI 应用

1. 访问 [讯飞 AIUI 控制台](https://aiui.xfyun.cn/app/)
2. 创建新应用，记录以下信息：
   - **APPID**
   - **APIKEY** 
   - **APISECRET**
3. 在应用设置中开启：
   - ✅ 语音听写 (IAT)
   - ✅ 语义理解 (NLP)
   - ✅ 语音合成 (TTS)

### 3. 配置密钥

修改代码中的认证信息（示例在左上角）：

```python
APPID = ""
APIKEY = ""
APISECRET = ""
```

## 🎯 使用指南

### asr3.py - 连续语音对话（推荐）

**全自动模式，适合机器狗/机器人部署**

```bash
python asr3.py
```

**功能特性：**
- 🎙️ 持续监听麦克风，无需按键
- 🔊 AI 回答自动语音播放
- 🚫 回声消除：AI 说话时自动静音麦克风
- ✋ 支持打断：用户说话时 AI 立即停止
- 🔄 自动重连，适合长时间运行

**操作流程：**
1. 直接对麦克风说话
2. 实时显示识别文字
3. AI 自动回答并播放语音
4. 可随时插话打断当前回答

### asr1.py - 单次语音对话

**读取本地音频文件进行识别**

```bash
# 先录制音频（使用 asr2.py）
python asr2.py

# 然后识别
python asr1.py  # 读取 input.pcm
```

### asr2.py - 录音工具

录制麦克风音频保存为 `input.pcm`

```bash
python asr2.py
# 按 Enter 停止录音
```

### asr.py - 文本交互

纯文字对话，无语音功能

```bash
python asr.py
```

## 📋 系统要求

| 项目 | 要求 |
|------|------|
| Python | 3.8+ |
| 麦克风 | 16kHz, 16bit, 单声道 |
| 网络 | 可访问 aiui.xf-yun.com |
| 平台 | Windows / Linux / macOS |

## 🔧 故障排查

| 问题 | 解决方案 |
|------|----------|
| 没有声音 | 检查 `pygame` 是否安装，系统音量是否正常 |
| 录音失败 | 检查麦克风权限，确认无其他程序占用 |
| 识别为乱码 | 确认音频格式为 16kHz, 16bit, 单声道 PCM |
| 无语音回答 | 检查 AIUI 控制台是否开启 TTS 功能 |

## 📚 参考文档

- [讯飞 AIUI 官方文档](https://aiui-doc.xf-yun.com/project-1/doc-584/)
- [WebSocket API 说明](https://aiui-doc.xf-yun.com/project-1/doc-585/)

## 📄 许可证

MIT License
