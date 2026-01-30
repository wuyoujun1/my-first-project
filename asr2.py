import sounddevice as sd
import numpy as np

# 录制 5 秒
duration = 3
recording = sd.rec(int(duration * 16000), samplerate=16000, channels=1, dtype=np.int16)
sd.wait()

# 保存为 PCM
recording.tofile("input.pcm")