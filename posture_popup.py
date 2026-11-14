import sys
import os
import json
import time
import threading
import tkinter as tk
from tkinter import font as tkfont

from sound_effects import (
    play_progressive_warning,
    play_success_sound,
    play_voice_fuck_you_issa
)

class PosturePopupWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Posture Guardian Alert")
        self.root.geometry("460x260")
        self.root.minsize(440, 240)
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#1E1E24")

        # Position at top right corner of primary screen
        try:
            screen_width = self.root.winfo_screenwidth()
            pos_x = max(10, screen_width - 490)
            self.root.geometry(f"+{pos_x}+50")
        except Exception:
            pass

        # Card container for normal posture alerts
        self.card = tk.Frame(self.root, bg="#2A2A36", bd=2, relief="ridge")
        self.card.pack(fill="both", expand=True, padx=12, pady=12)

        # Header with icon and status
        self.header_frame = tk.Frame(self.card, bg="#2A2A36")
        self.header_frame.pack(fill="x", padx=16, pady=(12, 4))

        self.icon_label = tk.Label(self.header_frame, text="⚠️", font=("Segoe UI Emoji", 24), bg="#2A2A36", fg="#FFA500")
        self.icon_label.pack(side="left", padx=(0, 10))

        self.title_label = tk.Label(
            self.header_frame,
            text="POSTURE ALERT",
            font=("Segoe UI", 16, "bold"),
            bg="#2A2A36",
            fg="#FF4444"
        )
        self.title_label.pack(side="left")

        # Urgency Level Tag
        self.level_badge = tk.Label(
            self.header_frame,
            text="Level 1",
            font=("Segoe UI", 10, "bold"),
            bg="#552228",
            fg="#FFAAAA",
            padx=8,
            pady=2
        )
        self.level_badge.pack(side="right")

        # Warning Instruction Text
        self.msg_label = tk.Label(
            self.card,
            text="Please straighten your posture!",
            font=("Segoe UI", 13, "bold"),
            bg="#2A2A36",
            fg="#FFFFFF",
            wraplength=400,
            justify="left"
        )
        self.msg_label.pack(anchor="w", padx=16, pady=(6, 4))

        # Detail text (angles & tips)
        self.detail_label = tk.Label(
            self.card,
            text="OpenCV is monitoring your posture in real-time...",
            font=("Segoe UI", 10),
            bg="#2A2A36",
            fg="#B0B0C0",
            wraplength=400,
            justify="left"
        )
        self.detail_label.pack(anchor="w", padx=16, pady=(0, 8))

        # Bottom actions
        self.btn_frame = tk.Frame(self.card, bg="#2A2A36")
        self.btn_frame.pack(fill="x", padx=16, pady=(4, 10))

        self.dismiss_btn = tk.Button(
            self.btn_frame,
            text="Dismiss (Esc)",
            font=("Segoe UI", 9),
            bg="#3E3E50",
            fg="#FFFFFF",
            activebackground="#505068",
            activeforeground="#FFFFFF",
            relief="flat",
            padx=12,
            pady=4,
            command=self.hide_window
        )
        self.dismiss_btn.pack(side="right")

        self.status_tag = tk.Label(
            self.btn_frame,
            text="Live Tracking Active",
            font=("Segoe UI", 9, "italic"),
            bg="#2A2A36",
            fg="#707090"
        )
        self.status_tag.pack(side="left")

        self.root.bind("<Escape>", lambda e: self.hide_window())
        self.auto_close_job = None
        self.is_visible = True

        # Fullscreen "FUCK YOU ISSA" popup overlay window
        self.fullscreen_win = None
        self.fullscreen_timer = None
        self.main_text_label = None

    def hide_window(self):
        self.root.withdraw()
        self.is_visible = False

    def show_window(self):
        self.root.deiconify()
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.is_visible = True

    def trigger_alert(self, target, neck_angle, back_angle, warning_level=1, tip=""):
        if self.auto_close_job:
            self.root.after_cancel(self.auto_close_job)
            self.auto_close_job = None

        self.show_window()

        # Visual escalation based on warning level
        level_vol_pct = min(100, warning_level * 25)
        if warning_level >= 3:
            card_bg = "#481014"
            accent_fg = "#FF2233"
            badge_text = f"LEVEL {warning_level} (LOUD {level_vol_pct}%)"
            badge_bg = "#771120"
        elif warning_level == 2:
            card_bg = "#3A1519"
            accent_fg = "#FF4455"
            badge_text = f"LEVEL 2 (Volume {level_vol_pct}%)"
            badge_bg = "#5E1D24"
        else:
            card_bg = "#2F181B"
            accent_fg = "#FF6677"
            badge_text = "LEVEL 1 (Gentle 25%)"
            badge_bg = "#4B2025"

        self.card.configure(bg=card_bg, highlightbackground=accent_fg, highlightcolor=accent_fg)
        self.header_frame.configure(bg=card_bg)
        self.btn_frame.configure(bg=card_bg)
        self.icon_label.configure(text="🚨" if warning_level >= 3 else "⚠️", bg=card_bg, fg=accent_fg)
        self.title_label.configure(text="POSTURE WARNING", bg=card_bg, fg=accent_fg)
        self.msg_label.configure(bg=card_bg)
        self.detail_label.configure(bg=card_bg)
        self.status_tag.configure(bg=card_bg, fg="#FFAAAA")
        self.dismiss_btn.configure(bg="#552228")

        self.level_badge.configure(text=badge_text, bg=badge_bg, fg="#FFFFFF")

        target_str = str(target).upper()
        if target_str == "BOTH":
            self.msg_label.configure(text="Straighten BOTH your NECK and BACK!")
        elif target_str == "NECK":
            self.msg_label.configure(text="Straighten your NECK!")
        elif target_str == "BACK":
            self.msg_label.configure(text="Straighten your BACK!")
        else:
            self.msg_label.configure(text=f"Straighten your {target_str}!")

        info_text = f"Neck: {neck_angle:.1f}° | Back: {back_angle:.1f}°\n"
        if tip:
            info_text += f"Tip: {tip}"
        else:
            info_text += "Sit tall, align your ears over shoulders and back straight."
        if warning_level > 1:
            info_text += f"\nWarning persisting! Sound volume escalated ({level_vol_pct}%)."

        self.detail_label.configure(text=info_text)
        self.status_tag.configure(text="OpenCV is checking your posture now...")

    def trigger_corrected(self, neck_angle, back_angle):
        if not self.is_visible:
            return

        self.card.configure(bg="#1A3322", highlightbackground="#00CC66", highlightcolor="#00CC66")
        self.header_frame.configure(bg="#1A3322")
        self.btn_frame.configure(bg="#1A3322")
        self.icon_label.configure(text="✅", bg="#1A3322", fg="#00FF88")
        self.title_label.configure(text="POSTURE RESTORED", bg="#1A3322", fg="#00FF88")
        self.level_badge.configure(text="RESOLVED", bg="#205530", fg="#AAFFCC")
        self.msg_label.configure(
            text="Excellent job! Posture straightened.",
            bg="#1A3322",
            fg="#FFFFFF"
        )
        self.detail_label.configure(
            text=f"Neck: {neck_angle:.1f}° | Back: {back_angle:.1f}° - Alignment Healthy!\nAlarm volume reset to Level 1.",
            bg="#1A3322",
            fg="#AAFFCC"
        )
        self.status_tag.configure(text="Auto-dismissing in 2.5s...", bg="#1A3322", fg="#77DDAA")
        self.dismiss_btn.configure(bg="#225533")

        if self.auto_close_job:
            self.root.after_cancel(self.auto_close_job)
        self.auto_close_job = self.root.after(2500, self.hide_window)

    # -------------------------------------------------------------
    # Fullscreen "FUCK YOU ISSA" Pop-up Across Entire Screen
    # -------------------------------------------------------------
    def trigger_middle_finger(self):
        """Displays a bold 'FUCK YOU ISSA' popup across the entire screen."""
        if self.fullscreen_timer:
            self.root.after_cancel(self.fullscreen_timer)
            self.fullscreen_timer = None

        if self.fullscreen_win is None or not self.fullscreen_win.winfo_exists():
            self.fullscreen_win = tk.Toplevel(self.root)
            self.fullscreen_win.attributes("-fullscreen", True)
            self.fullscreen_win.attributes("-topmost", True)
            self.fullscreen_win.configure(bg="#0B0002")

            center_frame = tk.Frame(self.fullscreen_win, bg="#0B0002")
            center_frame.pack(expand=True, fill="both")

            top_emojis = tk.Label(
                center_frame,
                text="🖕  🖕  🖕",
                font=("Segoe UI Emoji", 54),
                fg="#FF1744",
                bg="#0B0002"
            )
            top_emojis.pack(expand=True, pady=(70, 0))

            # Bold text across the entire screen
            self.main_text_label = tk.Label(
                center_frame,
                text="FUCK YOU ISSA",
                font=("Impact", 100, "bold"),
                fg="#FF1744",
                bg="#0B0002"
            )
            self.main_text_label.pack(expand=True, pady=10)

            sub_text = tk.Label(
                center_frame,
                text="MIDDLE FINGER DETECTED\n(Lower your hand or press ESC / click to dismiss)",
                font=("Segoe UI", 18, "bold"),
                fg="#FFAAAA",
                bg="#0B0002",
                justify="center"
            )
            sub_text.pack(expand=True, pady=(0, 60))

            self.fullscreen_win.bind("<Escape>", lambda e: self.dismiss_middle_finger())
            self.fullscreen_win.bind("<Button-1>", lambda e: self.dismiss_middle_finger())
            self.fullscreen_win.bind("<space>", lambda e: self.dismiss_middle_finger())
        else:
            self.fullscreen_win.deiconify()
            self.fullscreen_win.lift()
            self.fullscreen_win.attributes("-topmost", True)

        # Auto-dismiss safety timer (3 seconds if not held or refreshed)
        self.fullscreen_timer = self.root.after(3000, self.dismiss_middle_finger)

    def dismiss_middle_finger(self):
        if self.fullscreen_timer:
            self.root.after_cancel(self.fullscreen_timer)
            self.fullscreen_timer = None
        if self.fullscreen_win and self.fullscreen_win.winfo_exists():
            self.fullscreen_win.withdraw()

    def close(self):
        if self.fullscreen_win and self.fullscreen_win.winfo_exists():
            self.fullscreen_win.destroy()
        self.root.destroy()

def stdin_listener(app):
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            action = data.get("action")
            if action == "ALERT":
                target = data.get("target", "POSTURE")
                neck_angle = data.get("neck_angle", 0.0)
                back_angle = data.get("back_angle", 0.0)
                warning_level = data.get("warning_level", 1)
                tip = data.get("tip", "")
                app.root.after(0, lambda: app.trigger_alert(target, neck_angle, back_angle, warning_level, tip))
            elif action == "CORRECTED":
                neck_angle = data.get("neck_angle", 0.0)
                back_angle = data.get("back_angle", 0.0)
                app.root.after(0, lambda: app.trigger_corrected(neck_angle, back_angle))
            elif action == "MIDDLE_FINGER":
                app.root.after(0, app.trigger_middle_finger)
            elif action == "MIDDLE_FINGER_DISMISS":
                app.root.after(0, app.dismiss_middle_finger)
            elif action == "CLOSE":
                app.root.after(0, app.hide_window)
            elif action == "QUIT":
                app.root.after(0, app.close)
                break
        except Exception as e:
            sys.stderr.write(f"Popup error: {e}\n")
            sys.stderr.flush()

def main():
    app = PosturePopupWindow()
    app.hide_window()

    thread = threading.Thread(target=stdin_listener, args=(app,), daemon=True)
    thread.start()

    app.root.mainloop()

if __name__ == "__main__":
    main()
