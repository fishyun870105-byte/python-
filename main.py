import pyaudiowpatch as pyaudio
import numpy as np
from faster_whisper import WhisperModel
import queue
import threading
import time
import translators as ts
import customtkinter as ctk

SAMPLE_RATE = 16000
SILENCE_THRESHOLD = 0.01  
SILENCE_DURATION = 0.45   
MAX_RECORD_TIME = 6.0     

audio_queue = queue.Queue()
last_text = ""

class FloatingSubtitleApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("即時懸浮翻譯")
        self.geometry("800x260")
        self.attributes("-topmost", True)      
        self.attributes("-alpha", 0.88)        
        self.overrideredirect(True)            

        ctk.set_appearance_mode("Dark")
        self.configure(fg_color="#1E1E2E")

        self.header_frame = ctk.CTkFrame(self, fg_color="#282A36", height=30, corner_radius=0)
        self.header_frame.pack(fill="x", side="top")

        self.title_label = ctk.CTkLabel(self.header_frame, text=" 🌐 Realtime English Translator (字幕模式)", font=("Segoe UI", 12, "bold"), text_color="#89B4FA")
        self.title_label.pack(side="left", padx=10)

        self.close_button = ctk.CTkButton(self.header_frame, text="✕", width=30, height=25, fg_color="transparent", hover_color="#F38BA8", command=self.destroy)
        self.close_button.pack(side="right", padx=5)

        self.header_frame.bind("<ButtonPress-1>", self.start_move)
        self.header_frame.bind("<B1-Motion>", self.do_move)
        self.title_label.bind("<ButtonPress-1>", self.start_move)
        self.title_label.bind("<B1-Motion>", self.do_move)

        self.textbox = ctk.CTkTextbox(
            self, 
            font=("Microsoft JhengHei UI", 15, "bold"), 
            text_color="#A6E3A1", 
            fg_color="#181825", 
            corner_radius=8,
            wrap="word"
        )
        self.textbox.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.textbox.insert("end", "🔤 準備就緒，播放英文語音即可即時顯示字幕...\n\n")
        self.textbox.configure(state="disabled") # 設為唯讀防止誤觸修改

    def start_move(self, event):
        self.x = event.x
        self.y = event.y

    def do_move(self, event):
        deltax = event.x - self.x
        deltay = event.y - self.y
        x = self.winfo_x() + deltax
        y = self.winfo_y() + deltay
        self.geometry(f"+{x}+{y}")

    def add_subtitle(self, en_text, zh_text):
        self.textbox.configure(state="normal")
        
        new_entry = f"🇬🇧 {en_text}\n🔤 {zh_text}\n" + "-"*40 + "\n"
        self.textbox.insert("end", new_entry)
      
        self.textbox.see("end")
        self.textbox.configure(state="disabled")

def safe_translate(text):
    try:
        translated = ts.translate_text(text, translator='bing', from_language='en', to_language='zh-Hant', timeout=1.8)
        return translated
    except Exception:
        return "[翻譯超時]"

def process_audio(app, model):
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
                
                if original_text and len(original_text) > 2:
                    if original_text != last_text:
                        last_text = original_text
                        translated_text = safe_translate(original_text)
                        
                        # 即時新增並滾動顯示字幕
                        app.after(0, app.add_subtitle, original_text, translated_text)
                        
            except Exception as e:
                pass

def start_audio_stream():
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
    except Exception:
        p.terminate()
        return None, None

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

    stream = p.open(
        format=pyaudio.paFloat32,
        channels=default_speakers["maxInputChannels"],
        rate=int(default_speakers["defaultSampleRate"]),
        input=True,
        input_device_index=default_speakers["index"],
        frames_per_buffer=int(SAMPLE_RATE * 0.1),
        stream_callback=callback
    )
    return p, stream

if __name__ == "__main__":
    app = FloatingSubtitleApp()

    print("🚀 載入 Whisper (small.en) 模型中...")
    model = WhisperModel("small.en", device="cpu", compute_type="int8", cpu_threads=4)

    p, stream = start_audio_stream()
    if stream:
        stream.start_stream()

    threading.Thread(target=process_audio, args=(app, model), daemon=True).start()

    app.mainloop()

    if stream:
        stream.stop_stream()
        stream.close()
    if p:
        p.terminate()
