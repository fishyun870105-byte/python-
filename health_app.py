import threading
import webbrowser
import tempfile
import sounddevice as sd
import scipy.io.wavfile as wav
import customtkinter as ctk
import speech_recognition as sr
import time

# 設定 CustomTkinter 暖色質感外觀
ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("blue")

# --- 衛教影音與文字資料庫 ---
HEALTH_DATABASE = {
    "血壓": {
        "url": "https://youtu.be/StrBf3zvG-k?si=NYFhgEssjX5aqFvs",
        "title": "🩸 治療高血壓 改變從現在開始",
        "text": (
            "📓 控制高血壓包含四大要點：\n"
            "• 生活調整、定時監測、血壓控制、減少波動\n"
            "• 請務必遵照醫囑按時服藥，切勿自行停藥。"
        ),
    },
    "血糖": {
        "url": "https://youtu.be/Raa_LrNPhGs?si=56i7GTP6ugAdb6_B",
        "title": "🍬 控制血糖 輕鬆上手",
        "text": (
            "📓 控制血糖可以透過以下方式進行：\n"
            "• 透過均衡飲食、規律運動與藥物來共同管理\n"
            "• 請和醫師討論最適合您的血糖控制計畫。"
        ),
    },
    "糖尿病": {
        "url": "https://youtu.be/Raa_LrNPhGs?si=56i7GTP6ugAdb6_B",
        "title": "🍬 控制血糖 輕鬆上手",
        "text": (
            "📓 控制血糖可以透過以下方式進行：\n"
            "• 透過均衡飲食、規律運動與藥物來共同管理\n"
            "• 請和醫師討論最適合您的血糖控制計畫。"
        ),
    },
    "關節": {
        "url": "https://www.youtube.com/watch?v=example3",
        "title": "🦵 膝蓋關節保健運動",
        "text": (
            "📓 關節與膝蓋日常保健重點：\n"
            "• 避免長期負重與頻繁上下蹲跳。\n"
            "• 注意膝關節保暖，避免受涼。\n"
            "• 可在醫師指導下進行溫和肌力訓練。"
        ),
    },
    "膝蓋": {
        "url": "https://www.youtube.com/watch?v=example3",
        "title": "🦵 膝蓋關節保健運動",
        "text": (
            "📓 關節與膝蓋日常保健重點：\n"
            "• 避免長期負重與頻繁上下蹲跳。\n"
            "• 注意膝關節保暖，避免受涼。\n"
            "• 可在醫師指導下進行溫和肌力訓練。"
        ),
    },
}


class WarmYouTubeHealthApp(ctk.CTk):

  def __init__(self):
    super().__init__()

    # 視窗基本設定
    self.title("健康衛教小幫手")
    self.geometry("820x560")
    self.configure(fg_color="#FDF8F2")  # 柔和奶茶白背景
    self.overrideredirect(True)  # 移除傳統邊框

    # --- 1. 頂部自製暖色標題列 (可拖曳視窗) ---
    self.header = ctk.CTkFrame(
        self, fg_color="#F4ECE1", height=50, corner_radius=12
    )
    self.header.pack(fill="x", padx=15, pady=(15, 10))

    self.title_label = ctk.CTkLabel(
        self.header,
        text="  🏥 健康衛教小幫手",
        font=("Microsoft JhengHei UI", 16, "bold"),
        text_color="#D97706",
    )
    self.title_label.pack(side="left", padx=10)

    # 右上角關閉按鈕
    self.close_btn = ctk.CTkButton(
        self.header,
        text="✕",
        width=32,
        height=32,
        corner_radius=8,
        fg_color="#E7D7C9",
        hover_color="#F87171",
        text_color="#57534E",
        font=("Segoe UI", 14, "bold"),
        command=self.destroy,
    )
    self.close_btn.pack(side="right", padx=10)

    # 綁定頂部拖曳事件
    self.header.bind("<ButtonPress-1>", self.start_move)
    self.header.bind("<B1-Motion>", self.do_move)
    self.title_label.bind("<ButtonPress-1>", self.start_move)
    self.title_label.bind("<B1-Motion>", self.do_move)

    # --- 2. 中央主內容卡片區塊 ---
    self.main_card = ctk.CTkFrame(
        self,
        fg_color="#FFFFFF",
        corner_radius=16,
        border_width=1,
        border_color="#E7D7C9",
    )
    self.main_card.pack(fill="both", expand=True, padx=15, pady=(0, 10))

    # 動態狀態提示標籤
    self.status_label = ctk.CTkLabel(
        self.main_card,
        text="🎙️ 點擊下方按鈕，說出想查詢的內容（例如：血壓、血糖、膝蓋）",
        font=("Microsoft JhengHei UI", 16, "bold"),
        text_color="#B45309",
    )
    self.main_card.pack_propagate(False)
    self.status_label.pack(anchor="w", padx=25, pady=(20, 10))

    # 資訊顯示文字框
    self.textbox = ctk.CTkTextbox(
        self.main_card,
        font=("Microsoft JhengHei UI", 17),
        text_color="#292524",
        fg_color="transparent",
        wrap="word",
    )
    self.textbox.pack(fill="both", expand=True, padx=20, pady=10)

    # 設定綠色文字的 tag
    self.textbox.tag_config("green_tag", foreground="#059669")

    self.textbox.insert(
        "end",
        "💡 歡迎使用！請點擊下方橘色按鈕開始語音提問。\n\n"
        "您可以對著麥克風說：\n"
        "  • 「血壓要怎麼控制？」\n"
        "  • 「血糖控制該注意什麼？」\n"
        "  • 「膝蓋關節痛怎麼辦？」\n\n"
        "系統將自動為您播放相關的衛教影片與重點說明。",
    )

    # --- 3. 底部精緻控制列 ---
    self.footer_frame = ctk.CTkFrame(self, fg_color="transparent", height=60)
    self.footer_frame.pack(fill="x", padx=15, pady=(0, 15))

    # 語音聆聽按鈕
    self.mic_btn = ctk.CTkButton(
        self.footer_frame,
        text="🎙 開始語音提問",
        font=("Microsoft JhengHei UI", 17, "bold"),
        fg_color="#F59E0B",
        hover_color="#D97706",
        text_color="#FFFFFF",
        height=48,
        corner_radius=24,
        command=self.start_listening_thread,
    )
    self.mic_btn.pack(side="left", fill="x", expand=True, padx=(0, 8))

    # 清除重設按鈕
    self.clear_btn = ctk.CTkButton(
        self.footer_frame,
        text="清除畫面",
        font=("Microsoft JhengHei UI", 15),
        fg_color="#E7D7C9",
        hover_color="#D6C4B4",
        text_color="#44403C",
        width=110,
        height=48,
        corner_radius=24,
        command=self.clear_screen,
    )
    self.clear_btn.pack(side="right")

  # --- 視窗拖曳核心邏輯 ---
  def start_move(self, event):
    self.x = event.x
    self.y = event.y

  def do_move(self, event):
    deltax = event.x - self.x
    deltay = event.y - self.y
    x = self.winfo_x() + deltax
    y = self.winfo_y() + deltay
    self.geometry(f"+{x}+{y}")

  def clear_screen(self):
    self.textbox.delete("1.0", "end")
    self.textbox.insert(
        "end",
        "💡 歡迎使用！請點擊下方橘色按鈕開始語音提問。\n\n"
        "您可以對著麥克風說：\n"
        "  • 「血壓要怎麼控制？」\n"
        "  • 「血糖控制該注意什麼？」\n"
        "  • 「膝蓋關節痛怎麼辦？」\n\n"
        "系統將自動為您播放相關的衛教影片與重點說明。",
    )
    self.status_label.configure(
        text="🎙 畫面已重設，請點擊下方按鈕重新提問", text_color="#B45309"
    )

  # --- 背景語音聆聽與 YouTube 連結觸發 ---
  def start_listening_thread(self):
    self.mic_btn.configure(
        state="disabled", text="⏳ 正在聆聽中...", fg_color="#FBBF24"
    )
    self.status_label.configure(
        text="🎙 請清晰說出想查詢的健康主題...", text_color="#B45309"
    )
    threading.Thread(target=self.process_voice_query, daemon=True).start()

  def process_voice_query(self):
    try:
      time.sleep(0.5)
      duration = 6  # 錄音 6 秒
      fs = 16000  # 取樣率

      # 使用 sounddevice 錄音（指定正確的編號 2 麥克風）
      audio_data = sd.rec(
          int(duration * fs),
          samplerate=fs,
          channels=1,
          dtype="int16",
          device=2,
      )
      sd.wait()

      self.after(
          0,
          lambda: self.status_label.configure(
              text="🔍 正在為您查找衛教資訊...", text_color="#B45309"
          ),
      )

      # 存成暫存檔給 google 語音辨識使用
      with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
        wav.write(f.name, fs, audio_data)
        temp_path = f.name

      recognizer = sr.Recognizer()
      with sr.AudioFile(temp_path) as source:
        audio = recognizer.record(source)

      user_query = recognizer.recognize_google(audio, language="zh-TW")
      print(f"使用者提問：{user_query}")

      matched_key = None
      for key in HEALTH_DATABASE:
        if key in user_query:
          matched_key = key
          break

      if matched_key:
        info = HEALTH_DATABASE[matched_key]
        display_text = (
            f"🔍 您查詢的主題：「{user_query}」\n\n"
            f"🎬 【 {info['title']} 】\n"
            f"{info['text']}\n\n"
            f"✅ 觀賞完影片請參考上方衛教重點"
        )
        self.after(
            0,
            lambda: self.update_textbox_with_keyword(
                display_text, "✅ 觀賞完影片請參考上方衛教重點"
            ),
        )
        self.after(
            0,
            lambda: self.status_label.configure(
                text="▶️ 已為您自動開啟對應的 YouTube 衛教影片，請觀賞。",
                text_color="#059669",
            ),
        )
        webbrowser.open(info["url"])
      else:
        display_text = (
            f"🔍 您查詢的主題：「{user_query}」\n\n"
            "⚠️ 目前資料庫中暫無此主題的對應影片。\n"
            "建議您可以試著詢問「血壓」、「血糖」或「膝蓋」。"
        )
        self.after(0, lambda: self.update_textbox(display_text))
        self.after(
            0,
            lambda: self.status_label.configure(
                text="⚠️ 找不到相符主題", text_color="#DC2626"
            ),
        )

    except sr.UnknownValueError:
      self.after(
          0,
          lambda: self.status_label.configure(
              text="⚠️ 聽不清楚，請稍微靠近麥克風再說一次。", text_color="#DC2626"
          ),
      )
    except Exception as e:
      err_msg = str(e)
      self.after(
          0,
          lambda msg=err_msg: self.status_label.configure(
              text=f"⚠ 發生錯誤: {msg}", text_color="#DC2626"
          ),
      )
    finally:
      self.after(
          0,
          lambda: self.mic_btn.configure(
              state="normal", text="🎙️ 開始語音提問", fg_color="#F59E0B"
          ),
      )

  def update_textbox(self, text):
    self.textbox.delete("1.0", "end")
    self.textbox.insert("end", text)

  def update_textbox_with_keyword(self, text, keyword):
    self.textbox.delete("1.0", "end")
    self.textbox.insert("end", text)

    # 用程式自動在文字框中搜尋關鍵字的位置並上色
    pos = "1.0"
    while True:
      pos = self.textbox.search(keyword, pos, stopindex="end")
      if not pos:
        break
      end_pos = f"{pos}+{len(keyword)}c"
      self.textbox.tag_add("green_tag", pos, end_pos)
      pos = end_pos


if __name__ == "__main__":
  app = WarmYouTubeHealthApp()
  app.mainloop()
