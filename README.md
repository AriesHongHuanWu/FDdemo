# 🧠 AI 跌倒偵測系統 (Fall Detection System)

> 利用 **YOLOv8 目標辨識** + **CustomTkinter 圖形介面** + **Discord Bot 即時通知**，打造可實際部署的「智慧跌倒警報系統」。

---

## 📘 專案簡介

此系統能夠透過電腦攝影機 **即時監控畫面**，以 **YOLOv8 模型** 偵測人物姿態與床區重疊率，判斷是否發生跌倒。  
若檢測到跌倒事件，系統會：

1. 立即播放警報聲。  
2. 將即時畫面或短影片上傳至 Discord 頻道。  
3. 在介面上顯示警報狀態。  
4. 自動記錄事件到本地 `fall_log.txt`。

此系統適合應用於：
- 醫療照護機構（如安養院）
- 居家長者照護
- 實驗室安全監控
- 智慧居家整合系統

---

## 🧩 系統架構與邏輯說明

main.py  
│  
├── Discord 模組  
│　 ├── MyDiscordClient：啟動並監控 Discord Bot  
│　 ├── send_fall_alert_photo()：上傳即時跌倒圖片  
│　 ├── send_fall_alert_video()：上傳10秒跌倒影片  
│　 └── maintain_channel_history()：維持頻道訊息最新5則  
│  
├── GUI 主介面 (CustomTkinter)  
│　 ├── FallDetectionApp()：主視窗，統籌各分頁  
│　 │　 ├── WelcomePage()：首頁與說明  
│　 │　 ├── SettingsPage()：設定相機、床區範圍與警報閾值  
│　 │　 └── DetectionPage()：主偵測畫面  
│　 │  
│　 └── 工具函式  
│　　　├── intersection_area()：計算人與床區重疊面積  
│　　　├── scale_to_max_size()：影像縮放  
│　　　└── add_infrared_effect()：紅外線模式視覺化  
│  
├── YOLOv8 模型推論  
│　 ├── 使用 ultralytics.YOLO("yolov8n.pt")  
│　 ├── 檢測人物框（cls==0）  
│　 ├── 判斷寬高比 ratio 與床區重疊率 bed_coverage  
│　 └── 以時間閾值 fall_threshold 判定「跌倒中」  
│  
├── 警報邏輯  
│　 ├── ratio ≥ 1.05 → 疑似橫倒  
│　 ├── 超過 fall_threshold 秒 → 確認跌倒  
│　 ├── play_alarm() 播放警報音  
│　 ├── Discord 通知  
│　 └── record_fall_segment() 紀錄影片後自動刪除  
│  
└── 執行流程  
　　1️⃣ 執行 main.py  
　　2️⃣ 自動啟動 Discord Bot  
　　3️⃣ 顯示主畫面  
　　4️⃣ 進入「設定頁」選擇相機與床區  
　　5️⃣ 點擊「開始偵測」→ 實時檢測畫面  

---

## ⚙️ 環境需求

| 套件 | 功能 | 安裝指令 |
|------|------|-----------|
| opencv-python | 影像處理 | `pip install opencv-python` |
| numpy | 數據處理 | `pip install numpy` |
| Pillow | 圖像轉換 | `pip install Pillow` |
| customtkinter | GUI 主介面 | `pip install customtkinter` |
| ultralytics | YOLOv8 模型 | `pip install ultralytics` |
| discord.py | Discord Bot | `pip install discord.py` |

> Windows 使用者需安裝 `winsound`（內建於 Windows）

---

## 🚀 使用方式

### 1. 建立 Discord Bot
1. 前往 [Discord Developer Portal](https://discord.com/developers/applications)  
2. 建立新應用程式 → 建立 Bot  
3. 啟用「MESSAGE CONTENT INTENT」  
4. 取得 Bot Token，並邀請至伺服器  
5. 複製欲接收通知的頻道 ID  

### 2. 設定環境變數（安全建議）
```bash
setx DISCORD_TOKEN "你的 Token"
setx CHANNEL_ID "你的頻道 ID"
```

或直接修改程式中的：
```python
DISCORD_TOKEN = "你的token"
CHANNEL_ID = 123456789012345678
```

### 3. 啟動程式
```bash
python main.py
```

### 4. 操作流程
1. 進入設定頁面 → 選擇相機索引（通常為 0）  
2. 滑鼠拖曳畫面設定床區矩形範圍  
3. 設定跌倒時間閾值（例如 0.5 秒）  
4. 返回主頁面 → 點擊「開始偵測」  
5. 系統會顯示即時畫面，標示人物與床區，若偵測跌倒則觸發警報與 Discord 通知。

---

## 🧠 偵測邏輯

| 條件 | 狀態 | 說明 |
|------|------|------|
| 未偵測到人 | No User Detected | 無人入鏡 |
| 人在床上 | In Bed | 人框與床區重疊率 ≥ 50% |
| 人離床但站立 | Out of Bed | 寬高比 < 1.05 |
| 人離床且橫倒 | Falling | 寬高比 ≥ 1.05 且超過設定秒數 |

---

## 🌈 介面特色

- 深色主題：CustomTkinter + 綠色主題  
- 全螢幕設計：自適應解析度  
- 紅外線模式：模擬夜間偵測畫面  
- 即時時鐘顯示  
- Discord 照片/影片同步  
- 短影片自動刪除節省空間  

---

## 🧾 日誌紀錄

系統會自動建立 `fall_log.txt`，每當偵測跌倒，會新增：
```
YYYY-MM-DD HH:MM:SS - FALL DETECTED
```

---

## 🧱 專案結構

📂 FallDetectionSystem  
├── main.py　　　　　　# 主程式  
├── background.jpg　　　# 背景圖 (可選)  
├── fall_log.txt　　　　# 跌倒紀錄  
├── requirements.txt　　# 套件需求  
└── README.md　　　　　# 專案說明文件  

---

## 🔐 安全建議

- 請勿將 `DISCORD_TOKEN` 寫死在程式中。  
- 使用 `.env` 或系統環境變數儲存敏感資訊。  
- 若專案上傳到 GitHub，務必刪除 Token 相關內容。  

---

## 🧭 未來可擴充方向

- 整合 Firebase 或 LINE Notify 雲端警報  
- 加入 OpenVINO / TensorRT 加速 YOLO 推論  
- 支援多攝影機與遠端監控  
- 引入 Pose Estimation 強化準確率  

---

## 🧑‍💻 作者

**Aries Wu**  
AI × Robotics × Music 創作者  
📧 arieswu001@gmail.com  

