import cv2
import numpy as np
import threading
import time
import platform
import tkinter as tk
from tkinter import messagebox
from PIL import Image
import customtkinter as ctk
from ultralytics import YOLO
import discord
import asyncio
import io
import collections
import os

# ──────────────────────────────────────────────────────────
# Discord Bot Settings – 建議改用環境變數或外部設定檔
DISCORD_TOKEN = 'MTM1NDY0NjMxMjk5MzE2MTM3Nw.G1gZQS.bHAtNjWM7KnGIw-pAI0piNPhPms8bzu7qTClXs'
CHANNEL_ID = 1354646710063862051  # 替換成用來接收警報的頻道 ID

discord_client = None

# ──────────────────────────────────────────────────────────
# Discord Bot: keep only the latest messages
async def maintain_channel_history(client: discord.Client, channel_id: int, keep: int = 5):
    channel = client.get_channel(channel_id)
    if channel:
        messages = [msg async for msg in channel.history(limit=None)]
        if len(messages) > keep:
            messages_to_delete = messages[keep:]
            try:
                await channel.delete_messages(messages_to_delete)
                print(f"Deleted {len(messages_to_delete)} old messages.")
            except discord.HTTPException:
                print("Bulk delete failed; deleting one by one…")
                for msg in messages_to_delete:
                    try:
                        await msg.delete()
                    except Exception as e:
                        print("Failed to delete a message:", e)
    else:
        print("[Discord] Channel not found when maintaining history.")

# ──────────────────────────────────────────────────────────
# Discord Bot functions & classes
class MyDiscordClient(discord.Client):
    async def on_ready(self):
        print(f"[Discord] Logged in as {self.user}")

async def send_fall_alert_photo(client: discord.Client, frame=None):
    channel = client.get_channel(CHANNEL_ID)
    if channel:
        now = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        alert_message = f"Alert: Fall detected!\nDate/Time: {now}"
        file = None
        if frame is not None:
            ret, jpeg = cv2.imencode('.jpg', frame)
            if ret:
                file_bytes = io.BytesIO(jpeg.tobytes())
                file = discord.File(fp=file_bytes, filename="fall.jpg")
        await channel.send(alert_message, file=file)
        await maintain_channel_history(client, CHANNEL_ID, keep=5)
    else:
        print("[Discord] Channel not found!")

async def send_fall_alert_video(client: discord.Client, video_path):
    channel = client.get_channel(CHANNEL_ID)
    if channel:
        now = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        alert_message = f"Fall video recorded!\nDate/Time: {now}"
        try:
            await channel.send(alert_message, file=discord.File(video_path, filename=os.path.basename(video_path)))
            await maintain_channel_history(client, CHANNEL_ID, keep=5)
        except Exception as e:
            print("Failed to send video:", e)
    else:
        print("[Discord] Channel not found!")

def run_discord_bot():
    global discord_client
    intents = discord.Intents.default()
    discord_client = MyDiscordClient(intents=intents)
    discord_client.run(DISCORD_TOKEN)

# ──────────────────────────────────────────────────────────
# Alarm function
if platform.system() == "Windows":
    import winsound
    def play_alarm():
        winsound.Beep(1000, 500)
else:
    def play_alarm():
        print("Alarm Sound!")

# ──────────────────────────────────────────────────────────
# Helper functions
def intersection_area(boxA, boxB):
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])
    inter_width = max(0, xB - xA)
    inter_height = max(0, yB - yA)
    return inter_width * inter_height

def scale_to_max_size(orig_w, orig_h, max_w, max_h):
    ratio = min(max_w / float(orig_w), max_h / float(orig_h))
    return int(orig_w * ratio), int(orig_h * ratio)

def add_infrared_effect(frame_bgr):
    """Simple infrared-like effect using OpenCV's COLORMAP_INFERNO."""
    return cv2.applyColorMap(frame_bgr, cv2.COLORMAP_INFERNO)

# ──────────────────────────────────────────────────────────
# Main App GUI
class FallDetectionApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Fall Detection System")
        self.attributes("-fullscreen", True)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("green")

        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        try:
            bg_image = Image.open("background.jpg")
            bg_image = bg_image.resize((screen_width, screen_height), Image.Resampling.LANCZOS)
            bg_ctk_image = ctk.CTkImage(dark_image=bg_image, size=(screen_width, screen_height))
            self.bg_label = ctk.CTkLabel(self, image=bg_ctk_image, text="")
            self.bg_label.place(relx=0, rely=0, relwidth=1, relheight=1)
        except Exception as e:
            print("Failed to load background image:", e)

        # Default settings
        self.camera_index = 0
        self.bed_areas = []
        self.fall_threshold = 0.5  # 秒
        self.discord_enabled = True

        # ───────── Top toolbar ─────────
        self.toolbar = ctk.CTkFrame(self, height=40, fg_color="transparent")
        self.toolbar.pack(side="top", fill="x", padx=10, pady=(10, 0))

        self.home_button = ctk.CTkButton(self.toolbar, text="Home", width=80,
                                         command=lambda: self.show_frame("WelcomePage"))
        self.home_button.pack(side="left", padx=5)

        self.settings_button = ctk.CTkButton(self.toolbar, text="Settings", width=80,
                                             command=lambda: self.show_frame("SettingsPage"))
        self.settings_button.pack(side="left", padx=5)

        self.exit_button = ctk.CTkButton(self.toolbar, text="Exit", width=80, command=self.destroy)
        self.exit_button.pack(side="left", padx=5)

        self.clock_label = ctk.CTkLabel(self.toolbar, text="", font=ctk.CTkFont(size=14))
        self.clock_label.pack(side="right", padx=10)
        self.update_clock()

        # ───────── Main container ─────────
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(expand=True, fill="both", padx=10, pady=10)

        self.frames = {}
        for F in (WelcomePage, SettingsPage, DetectionPage):
            page_name = F.__name__
            frame = F(parent=self.container, controller=self)
            self.frames[page_name] = frame
            frame.place(relwidth=1, relheight=1)

        self.show_frame("WelcomePage")

    def update_clock(self):
        now = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        self.clock_label.configure(text=now)
        self.clock_label.after(1000, self.update_clock)

    def show_frame(self, page_name):
        frame = self.frames[page_name]
        frame.tkraise()
        if page_name == "DetectionPage":
            frame.start_detection()

# ──────────────────────────────────────────────────────────
# Welcome Page
class WelcomePage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller

        ctk.CTkLabel(self, text="Welcome to Fall Detection System",
                     font=ctk.CTkFont(size=28, weight="bold")).pack(pady=(20, 10))

        ctk.CTkLabel(self,
                     text=("This system detects falls in real-time and sends Discord alerts.\n"
                           "Please ensure your camera and bed areas are set in 'Settings'."),
                     font=ctk.CTkFont(size=14)).pack(pady=(0, 20))

        ctk.CTkButton(self, text="Start Detection", width=220, height=40,
                      command=lambda: controller.show_frame("DetectionPage")).pack(pady=10)

# ──────────────────────────────────────────────────────────
# Settings Page
class SettingsPage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller

        self.video_label = ctk.CTkLabel(self, text="Camera Feed", width=640, height=480)
        self.video_label.grid(row=0, column=0, padx=(0, 10), pady=10, sticky="n")

        control_frame = ctk.CTkFrame(self, width=300)
        control_frame.grid(row=0, column=1, padx=10, pady=10, sticky="n")

        ctk.CTkLabel(control_frame, text="Camera Index:").pack(pady=(0, 5))
        self.cam_entry = ctk.CTkEntry(control_frame, placeholder_text="e.g., 0")
        self.cam_entry.pack(pady=5)

        ctk.CTkLabel(control_frame, text="Fall Detection Threshold (s):").pack(pady=(10, 5))
        self.fall_entry = ctk.CTkEntry(control_frame, placeholder_text="e.g., 1.0")
        self.fall_entry.pack(pady=5)

        self.discord_checkbox = ctk.CTkCheckBox(control_frame, text="Enable Discord Notifications")
        self.discord_checkbox.pack(pady=10)
        self.discord_checkbox.select()

        ctk.CTkLabel(control_frame, text="Bed Area List:").pack(pady=(15, 5))
        self.bed_listbox = tk.Listbox(control_frame, height=5)
        self.bed_listbox.pack(pady=5, fill="x")

        ctk.CTkButton(control_frame, text="Delete Selected", command=self.delete_selected_bed).pack(pady=(10, 5))
        ctk.CTkButton(control_frame, text="Save and Return", command=self.save_settings).pack(pady=(15, 0))

        self.cap = None
        self.running = True
        threading.Thread(target=self.video_loop, daemon=True).start()

        self.bed_start = None
        self.bed_end = None
        self.current_bed_rect = None

        self.video_label.bind("<ButtonPress-1>", self.on_mouse_down)
        self.video_label.bind("<B1-Motion>", self.on_mouse_drag)
        self.video_label.bind("<ButtonRelease-1>", self.on_mouse_up)

    def update_video_label(self, ctk_img):
        self.video_label.configure(image=ctk_img)
        self.video_label.image = ctk_img

    def video_loop(self):
        self.cap = cv2.VideoCapture(self.controller.camera_index, cv2.CAP_DSHOW)
        MAX_W, MAX_H = 640, 480
        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                continue

            # Draw current selection
            if self.current_bed_rect is not None:
                x1, y1, x2, y2 = self.current_bed_rect
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

            # Draw existing bed areas
            for rect in self.controller.bed_areas:
                cv2.rectangle(frame, (rect[0], rect[1]), (rect[2], rect[3]), (255, 0, 0), 2)

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(rgb)
            orig_w, orig_h = pil_img.size
            new_w, new_h = scale_to_max_size(orig_w, orig_h, MAX_W, MAX_H)
            pil_img = pil_img.resize((new_w, new_h), Image.Resampling.LANCZOS)

            ctk_img = ctk.CTkImage(dark_image=pil_img, size=(new_w, new_h))
            self.video_label.after(0, self.update_video_label, ctk_img)
            time.sleep(0.03)

    def on_mouse_down(self, event):
        self.bed_start = (event.x, event.y)

    def on_mouse_drag(self, event):
        if self.bed_start is None:
            return
        self.bed_end = (event.x, event.y)
        x1, y1 = self.bed_start
        x2, y2 = self.bed_end
        x1, x2 = sorted([x1, x2])
        y1, y2 = sorted([y1, y2])
        self.current_bed_rect = (x1, y1, x2, y2)

    def on_mouse_up(self, event):
        if self.current_bed_rect is not None:
            self.controller.bed_areas.append(self.current_bed_rect)
            self.bed_listbox.insert(tk.END, f"Bed: {self.current_bed_rect}")
        self.bed_start = None
        self.bed_end = None
        self.current_bed_rect = None

    def delete_selected_bed(self):
        selection = self.bed_listbox.curselection()
        if not selection:
            return
        index = selection[0]
        self.bed_listbox.delete(index)
        del self.controller.bed_areas[index]

    def save_settings(self):
        cam_text = self.cam_entry.get().strip()
        if cam_text.isdigit():
            self.controller.camera_index = int(cam_text)
        else:
            messagebox.showinfo("Alert", "Please enter a valid camera index (number)")
            return

        fall_text = self.fall_entry.get().strip()
        try:
            self.controller.fall_threshold = float(fall_text)
        except ValueError:
            messagebox.showinfo("Alert", "Please enter a valid fall detection threshold (seconds)")
            return

        self.controller.discord_enabled = self.discord_checkbox.get()
        self.running = False
        if self.cap is not None:
            self.cap.release()
        self.controller.show_frame("WelcomePage")

# ──────────────────────────────────────────────────────────
# Detection Page
class DetectionPage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller

        self.running = False
        self.detection_started = False
        self.fall_alarm_triggered = False
        self.falling_start_time = None
        self.last_alert_time = 0

        # Rolling buffer for short video
        self.frame_buffer = collections.deque(maxlen=35)

        # Infrared Mode switch (placed above YOLO feed)
        self.infrared_mode = False
        self.infrared_switch = ctk.CTkSwitch(
            self,
            text="Infrared Mode",
            command=self.toggle_infrared_mode
        )
        self.infrared_switch.pack(pady=10)

        self.info_label = ctk.CTkLabel(self, text="Time: --   Status: --", font=ctk.CTkFont(size=14))
        self.info_label.pack(pady=(10, 5))

        self.video_label = ctk.CTkLabel(self, text="Waiting for camera feed...")
        self.video_label.pack(pady=5)

        self.model = YOLO("yolov8n.pt")

        # >>> 1️⃣ 紅外線閃爍延遲計時器
        self.alert_ir_until = 0

    def toggle_infrared_mode(self):
        self.infrared_mode = not self.infrared_mode

    def update_video_label(self, ctk_img):
        if self.video_label.cget("text") != "":
            self.video_label.configure(text="")
        self.video_label.configure(image=ctk_img)
        self.video_label.image = ctk_img

    def update_info_label(self, status_text):
        current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        text = f"Time: {current_time}   Status: {status_text}"
        self.info_label.configure(text=text)

    def start_detection(self):
        if not self.detection_started:
            self.running = True
            self.cap = cv2.VideoCapture(self.controller.camera_index, cv2.CAP_DSHOW)
            self.detection_thread = threading.Thread(target=self.detection_loop, daemon=True)
            self.detection_thread.start()
            self.detection_started = True

    def detection_loop(self):
        MAX_W, MAX_H = 1280, 720
        user_status = "No User Detected"

        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                print("Cannot grab frame!")
                continue

            current_time = time.time()
            self.frame_buffer.append(frame.copy())

            user_status = "No User Detected"
            try:
                results = self.model(frame, imgsz=416)[0]
            except Exception as e:
                print("YOLO detection error:", e)
                results = None

            if results is not None and results.boxes is not None and len(results.boxes) > 0:
                for box in results.boxes:
                    coords = box.xyxy.cpu().numpy().flatten().astype(int)
                    if len(coords) < 4:
                        continue
                    x1, y1, x2, y2 = coords
                    width = x2 - x1
                    height = y2 - y1
                    cls = int(box.cls.cpu().numpy().item())
                    conf = float(box.conf.cpu().numpy().item())

                    if cls == 0 and conf > 0.5:  # person
                        ratio = width / float(height + 1e-5)
                        box_area = width * height
                        total_intersection = 0
                        for bed in self.controller.bed_areas:
                            total_intersection += intersection_area((x1, y1, x2, y2), bed)
                        total_intersection = min(total_intersection, box_area)
                        bed_coverage = total_intersection / (box_area + 1e-5)

                        if bed_coverage >= 0.5:
                            user_status = "In Bed"
                            self.falling_start_time = None
                            box_color = (0, 255, 0)
                        else:
                            if ratio >= 1.05:
                                if self.falling_start_time is None:
                                    self.falling_start_time = current_time
                                    user_status = "Out of Bed"
                                    box_color = (0, 255, 0)
                                elif current_time - self.falling_start_time >= self.controller.fall_threshold:
                                    user_status = "Falling"
                                    box_color = (0, 0, 255)
                                else:
                                    user_status = "Out of Bed"
                                    box_color = (0, 255, 0)
                            else:
                                user_status = "Out of Bed"
                                self.falling_start_time = None
                                box_color = (0, 255, 0)

                        cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, 2)
                        break
                    else:
                        user_status = "No User Detected"
                        self.falling_start_time = None
            else:
                self.falling_start_time = None

            # >>> 2️⃣ If falling
            if user_status == "Falling":
                cv2.putText(frame, "FALLING", (50, 50), cv2.FONT_HERSHEY_SIMPLEX,
                            1.2, (0, 0, 255), 3)

                if current_time - self.last_alert_time >= 10:
                    self.last_alert_time = current_time
                    self.alert_ir_until = current_time + 1  # 紅外線 1 秒
                    threading.Thread(target=play_alarm, daemon=True).start()

                    if self.controller.discord_enabled and discord_client is not None:
                        asyncio.run_coroutine_threadsafe(
                            send_fall_alert_photo(discord_client, frame), discord_client.loop
                        )
                    threading.Thread(target=self.record_fall_segment, daemon=True).start()

                    log_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                    with open("fall_log.txt", "a") as f:
                        f.write(f"{log_time} - FALL DETECTED\n")
            else:
                self.fall_alarm_triggered = False

            # Draw bed areas
            for bed in self.controller.bed_areas:
                cv2.rectangle(frame, (bed[0], bed[1]), (bed[2], bed[3]), (255, 0, 0), 2)

            # Update label
            self.info_label.after(0, self.update_info_label, user_status)

            # >>> 3️⃣ 套用紅外線效果（使用者開紅外線或處於警報閃爍時間內）
            if self.infrared_mode or current_time < self.alert_ir_until:
                frame = add_infrared_effect(frame)

            # Convert frame to PIL → CTkImage
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(rgb)
            orig_w, orig_h = pil_img.size
            new_w, new_h = scale_to_max_size(orig_w, orig_h, MAX_W, MAX_H)
            pil_img = pil_img.resize((new_w, new_h), Image.Resampling.LANCZOS)

            ctk_img = ctk.CTkImage(dark_image=pil_img, size=(new_w, new_h))
            self.video_label.after(0, self.update_video_label, ctk_img)

            time.sleep(0.2)  # around 5 fps

    def record_fall_segment(self):
        """Record ~10 s of video around the fall (7 s before + 3 s after)."""
        pre_event_frames = list(self.frame_buffer)
        additional_frames = []
        start_time = time.time()
        while time.time() - start_time < 3:
            ret, frame = self.cap.read()
            if ret:
                additional_frames.append(frame.copy())
            time.sleep(0.2)

        all_frames = pre_event_frames + additional_frames
        if all_frames:
            height, width = all_frames[0].shape[:2]
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            filename = f"fall_{time.strftime('%Y%m%d_%H%M%S')}.mp4"
            out = cv2.VideoWriter(filename, fourcc, 5.0, (width, height))

            for frm in all_frames:
                out.write(frm)
            out.release()
            print(f"Fall segment recorded: {filename}")

            if self.controller.discord_enabled and discord_client is not None:
                future = asyncio.run_coroutine_threadsafe(
                    send_fall_alert_video(discord_client, filename), discord_client.loop
                )
                try:
                    future.result(timeout=30)
                    print("Video sent to Discord successfully.")
                except Exception as e:
                    print("Video sending error:", e)

            if os.path.exists(filename):
                os.remove(filename)
                print(f"Local video file {filename} deleted.")
        else:
            print("No frames captured for fall segment.")

    def reset_alarm(self):
        self.fall_alarm_triggered = False

    def destroy(self):
        self.running = False
        if hasattr(self, "cap") and self.cap is not None:
            self.cap.release()
        super().destroy()

# ──────────────────────────────────────────────────────────
# Entry point
if __name__ == "__main__":
    # Launch Discord Bot
    threading.Thread(target=run_discord_bot, daemon=True).start()

    # Launch main app
    app = FallDetectionApp()
    app.mainloop()
