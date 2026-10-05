import pyaudiowpatch as pyaudio
import numpy as np
from faster_whisper import WhisperModel
import queue
import threading
import time
import translators as ts

# --- 參數設定 ---
SAMPLE_RATE = 16000
SILENCE_THRESHOLD = 0.01  
SILENCE_DURATION = 0.6  
MAX_RECORD_TIME = 6.0     

audio_queue = queue.Queue()

print("🚀 正在載入動態斷句模型 (small.en)...")
model = WhisperModel("small.en", device="cpu", compute_type="int8", cpu_threads=4)
print("✅ 模型載入完成！")

last_text = ""

def safe_translate(text):
    """將完整的英文句子翻譯為繁體中文"""
    try:
        translated = ts.translate_text(text, translator='bing', from_language='en', to_language='zh-Hant', timeout=1.8)
        return translated
    except Exception:
        return "[翻譯超時]"

def process_audio():
    global last_text
    audio_buffer = []
    silence_counter = 0
    
    
    frames_per_second = 10  
    silence_frames_needed = int(SILENCE_DURATION * frames_per_second)
    max_frames_needed = int(MAX_RECORD_TIME * frames_per_second)

    while True:
        chunk = audio_queue.get()
        audio_buffer.append(chunk)
        
       
        rms = np.sqrt(np.mean(chunk**2))
        
        if rms < SILENCE_THRESHOLD:
            silence_counter += 1
        else:
            silence_counter = 0

       
        if (silence_counter >= silence_frames_needed and len(audio_buffer) > 5) or len(audio_buffer) >= max_frames_needed:
            full_audio = np.concatenate(audio_buffer)
            audio_buffer = []
            silence_counter = 0
            
            try:
                segments, info = model.transcribe(
                    full_audio, 
                    language="en", 
                    beam_size=2,
                    temperature=0.0,
                    vad_filter=True,
                    vad_parameters=dict(min_silence_duration_ms=300)
                )
                
                original_text = " ".join([segment.text.strip() for segment in segments]).strip()
                
                if original_text and len(original_text) > 3:
                    if original_text != last_text:
                        last_text = original_text
                        
                        translated_text = safe_translate(original_text)
                        
                        print(f"🇬🇧 英文: {original_text}")
                        print(f"🔤 中文: {translated_text}")
                        print("-" * 50)
                        
            except Exception as e:
                pass

def main():
    p = pyaudio.PyAudio()
    try:
        wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)
        default_speakers = p.get_device_info_by_index(wasapi_info["defaultOutputDevice"])
        
        if not default_speakers["isLoopbackDevice"]:
            for loopback in p.get_loopback_device_info_generator():
                if default_speakers["name"] in loopback["name"]:
                    default_speakers = loopback
                    break
            else:
                default_speakers = p.get_default_loopback_device_info()
                
        print(f"📢 擷取音訊裝置: {default_speakers['name']}")
    except Exception as e:
        print(f"❌ 音訊裝置初始化失敗: {e}")
        p.terminate()
        return

    threading.Thread(target=process_audio, daemon=True).start()
    
    print("\n🔴 開始自然語意即時翻譯！請播放英文語音 (按 Ctrl+C 停止)...")
    print("=" * 50)

    # 設置每次收集 0.1 秒的音訊區段
    chunk_samples = int(SAMPLE_RATE * 0.1)

    def callback(in_data, frame_count, time_info, status):
        audio_data = np.frombuffer(in_data, dtype=np.float32)
        
        channels = default_speakers.get("maxInputChannels", 2)
        if channels > 1:
            audio_data = audio_data.reshape(-1, channels).mean(axis=1)
            
        native_rate = int(default_speakers["defaultSampleRate"])
        if native_rate != SAMPLE_RATE:
            step = native_rate // SAMPLE_RATE
            audio_data = audio_data[::step]

        audio_queue.put(audio_data)
        return (in_data, pyaudio.paContinue)

    try:
        stream = p.open(
            format=pyaudio.paFloat32,
            channels=default_speakers["maxInputChannels"],
            rate=int(default_speakers["defaultSampleRate"]),
            input=True,
            input_device_index=default_speakers["index"],
            frames_per_buffer=chunk_samples,
            stream_callback=callback
        )
        stream.start_stream()
        
        while stream.is_active():
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\n🛑 已停止程式。")
    finally:
        p.terminate()

if __name__ == "__main__":
    main()