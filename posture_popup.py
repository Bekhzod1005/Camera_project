import sys
import json
import threading
import tkinter as tk

class NeckPopupWindow:
    """Lightweight, non-blocking desktop pop-up for neck posture warnings."""
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Neck Posture Guardian")
        self.root.geometry("440x230")
        self.root.minsize(420, 210)
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#1E1E24")

        # Position at top right corner of primary screen
        try:
            screen_width = self.root.winfo_screenwidth()
            pos_x = max(10, screen_width - 470)
            self.root.geometry(f"+{pos_x}+50")
        except Exception:
            pass

        # Card container
        self.card = tk.Frame(self.root, bg="#2A2A36", bd=2, relief="ridge")
        self.card.pack(fill="both", expand=True, padx=12, pady=12)

        # Header Frame
        self.header_frame = tk.Frame(self.card, bg="#2A2A36")
        self.header_frame.pack(fill="x", padx=16, pady=(12, 4))

        self.icon_label = tk.Label(self.header_frame, text="⚠️", font=("Segoe UI Emoji", 24), bg="#2A2A36", fg="#FFA500")
        self.icon_label.pack(side="left", padx=(0, 10))

        self.title_label = tk.Label(
            self.header_frame,
            text="NECK POSTURE ALERT",
            font=("Segoe UI", 15, "bold"),
            bg="#2A2A36",
            fg="#FF4444"
        )
        self.title_label.pack(side="left")

        self.level_badge = tk.Label(
            self.header_frame,
            text="Level 1",
            font=("Segoe UI", 9, "bold"),
            bg="#552228",
            fg="#FFAAAA",
            padx=8,
            pady=2
        )
        self.level_badge.pack(side="right")

        # Warning Instruction Text
        self.msg_label = tk.Label(
            self.card,
            text="Straighten your NECK!",
            font=("Segoe UI", 13, "bold"),
            bg="#2A2A36",
            fg="#FFFFFF",
            wraplength=380,
            justify="left"
        )
        self.msg_label.pack(anchor="w", padx=16, pady=(6, 4))

        # Angle & Tip Detail Text
        self.detail_label = tk.Label(
            self.card,
            text="OpenCV is monitoring your neck alignment in real time...",
            font=("Segoe UI", 10),
            bg="#2A2A36",
            fg="#B0B0C0",
            wraplength=380,
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
            pady=3,
            command=self.hide_window
        )
        self.dismiss_btn.pack(side="right")

        self.status_tag = tk.Label(
            self.btn_frame,
            text="Live Neck Tracking Active",
            font=("Segoe UI", 9, "italic"),
            bg="#2A2A36",
            fg="#707090"
        )
        self.status_tag.pack(side="left")

        self.root.bind("<Escape>", lambda e: self.hide_window())
        self.auto_close_job = None
        self.is_visible = True

    def hide_window(self):
        self.root.withdraw()
        self.is_visible = False

    def show_window(self):
        self.root.deiconify()
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.is_visible = True

    def trigger_alert(self, neck_angle, warning_level=1):
        if self.auto_close_job:
            self.root.after_cancel(self.auto_close_job)
            self.auto_close_job = None

        self.show_window()

        level_vol_pct = min(100, warning_level * 25)
        if warning_level >= 3:
            card_bg = "#481014"
            accent_fg = "#FF2233"
            badge_text = f"LEVEL {warning_level} (LOUD {level_vol_pct}%)"
            badge_bg = "#771120"
        elif warning_level == 2:
            card_bg = "#3A1519"
            accent_fg = "#FF4455"
            badge_text = f"LEVEL 2 ({level_vol_pct}% Vol)"
            badge_bg = "#5E1D24"
        else:
            card_bg = "#2F181B"
            accent_fg = "#FF6677"
            badge_text = "LEVEL 1 (25% Vol)"
            badge_bg = "#4B2025"

        self.card.configure(bg=card_bg, highlightbackground=accent_fg, highlightcolor=accent_fg)
        self.header_frame.configure(bg=card_bg)
        self.btn_frame.configure(bg=card_bg)
        self.icon_label.configure(text="🚨" if warning_level >= 3 else "⚠️", bg=card_bg, fg=accent_fg)
        self.title_label.configure(text="NECK POSTURE WARNING", bg=card_bg, fg=accent_fg)
        self.msg_label.configure(text="Straighten your NECK!", bg=card_bg)
        self.detail_label.configure(bg=card_bg)
        self.status_tag.configure(bg=card_bg, fg="#FFAAAA")
        self.dismiss_btn.configure(bg="#552228")
        self.level_badge.configure(text=badge_text, bg=badge_bg, fg="#FFFFFF")

        info_text = f"Current Neck Angle: {neck_angle:.1f}°\nTip: Tuck your chin slightly and align ears over shoulders."
        if warning_level > 1:
            info_text += f"\nSlouch persisting! Sound volume escalated ({level_vol_pct}%)."

        self.detail_label.configure(text=info_text)
        self.status_tag.configure(text="OpenCV checking neck alignment...")

    def trigger_corrected(self, neck_angle):
        if not self.is_visible:
            return

        self.card.configure(bg="#1A3322", highlightbackground="#00CC66", highlightcolor="#00CC66")
        self.header_frame.configure(bg="#1A3322")
        self.btn_frame.configure(bg="#1A3322")
        self.icon_label.configure(text="✅", bg="#1A3322", fg="#00FF88")
        self.title_label.configure(text="NECK POSITION RESTORED", bg="#1A3322", fg="#00FF88")
        self.level_badge.configure(text="ALIGNED", bg="#205530", fg="#AAFFCC")
        self.msg_label.configure(
            text="Excellent job! Neck straightened.",
            bg="#1A3322",
            fg="#FFFFFF"
        )
        self.detail_label.configure(
            text=f"Neck Angle: {neck_angle:.1f}° - Healthy Alignment!\nWarning level reset to 1.",
            bg="#1A3322",
            fg="#AAFFCC"
        )
        self.status_tag.configure(text="Auto-dismissing in 2.5s...", bg="#1A3322", fg="#77DDAA")
        self.dismiss_btn.configure(bg="#225533")

        if self.auto_close_job:
            self.root.after_cancel(self.auto_close_job)
        self.auto_close_job = self.root.after(2500, self.hide_window)

    def close(self):
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
                neck_angle = data.get("neck_angle", 0.0)
                warning_level = data.get("warning_level", 1)
                app.root.after(0, lambda: app.trigger_alert(neck_angle, warning_level))
            elif action == "CORRECTED":
                neck_angle = data.get("neck_angle", 0.0)
                app.root.after(0, lambda: app.trigger_corrected(neck_angle))
            elif action == "CLOSE":
                app.root.after(0, app.hide_window)
            elif action == "QUIT":
                app.root.after(0, app.close)
                break
        except Exception as e:
            sys.stderr.write(f"Popup error: {e}\n")
            sys.stderr.flush()

def main():
    app = NeckPopupWindow()
    app.hide_window()

    thread = threading.Thread(target=stdin_listener, args=(app,), daemon=True)
    thread.start()

    app.root.mainloop()

if __name__ == "__main__":
    main()
