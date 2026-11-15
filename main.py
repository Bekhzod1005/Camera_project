import os
import sys
import time
import math
import json
import argparse
import subprocess
from collections import deque
import cv2
import numpy as np

# Avoid matplotlib cache folder permission warnings on Windows
os.environ["MPLCONFIGDIR"] = os.environ.get("TEMP", ".")

import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from posture_analyzer import NeckPostureAnalyzer
from sound_effects import play_progressive_warning, play_success_sound

# --- Auto Model Downloader ---
def ensure_model_file(base_dir):
    """Ensure lightweight pose model is available, downloading if needed."""
    lite_path = os.path.join(base_dir, "pose_landmarker_lite.task")
    full_path = os.path.join(base_dir, "pose_landmarker_full.task")

    if os.path.exists(lite_path):
        return lite_path
    if os.path.exists(full_path):
        return full_path

    # Download lite model
    url = "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task"
    print("Downloading lightweight pose model (~5.5MB)...")
    import urllib.request
    urllib.request.urlretrieve(url, lite_path)
    print("Downloaded lightweight model successfully.")
    return lite_path

# --- Pop-up Controller Helper ---
class PopupController:
    """Manages the separate-process Tkinter popup window via stdin pipes."""
    def __init__(self):
        self.process = None
        base_dir = os.path.dirname(os.path.abspath(__file__))
        popup_script = os.path.join(base_dir, "posture_popup.py")

        try:
            self.process = subprocess.Popen(
                [sys.executable, popup_script],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
        except Exception as e:
            print(f"[Warning] Failed to start popup controller: {e}")

    def send(self, data):
        if self.process and self.process.poll() is None:
            try:
                line = json.dumps(data) + "\n"
                self.process.stdin.write(line)
                self.process.stdin.flush()
            except Exception as e:
                print(f"[Warning] Failed to send to popup: {e}")

    def trigger_alert(self, neck_angle, warning_level=1):
        self.send({
            "action": "ALERT",
            "neck_angle": float(neck_angle),
            "warning_level": int(warning_level)
        })

    def trigger_corrected(self, neck_angle):
        self.send({
            "action": "CORRECTED",
            "neck_angle": float(neck_angle)
        })

    def close(self):
        if self.process and self.process.poll() is None:
            try:
                self.send({"action": "QUIT"})
                self.process.terminate()
            except Exception:
                pass

# --- Visual Drawing Helpers ---
def draw_dashed_line(img, pt1, pt2, color, thickness=1, dash_len=6):
    dist = math.hypot(pt2[0] - pt1[0], pt2[1] - pt1[1])
    if dist == 0:
        return
    dashes = int(dist / dash_len)
    for i in range(0, dashes, 2):
        start = (
            int(pt1[0] + (pt2[0] - pt1[0]) * (i / dashes)),
            int(pt1[1] + (pt2[1] - pt1[1]) * (i / dashes))
        )
        end = (
            int(pt1[0] + (pt2[0] - pt1[0]) * ((i + 1) / dashes)),
            int(pt1[1] + (pt2[1] - pt1[1]) * ((i + 1) / dashes))
        )
        cv2.line(img, start, end, color, thickness)

def draw_hud(frame, metrics, analyzer, time_until_check, check_interval,
             state, sound_enabled, warning_level=1):
    """Render a lightweight, clean head-up display focused solely on neck alignment."""
    h, w, _ = frame.shape
    overlay = frame.copy()

    COLOR_GOOD = (70, 200, 70)       # Vibrant Green
    COLOR_WARN = (40, 160, 255)      # Orange
    COLOR_BAD = (40, 40, 240)        # Bright Red
    COLOR_MUTED = (160, 160, 160)    # Gray
    COLOR_BG = (22, 22, 28)          # Dark background
    COLOR_WHITE = (250, 250, 250)

    # 1. Draw Neck Alignment Vector (Mid-Shoulder to Mid-Ear)
    if metrics.is_detected:
        ear = metrics.ear_pt            # Middle of the ears (Head Center)
        shoulder = metrics.shoulder_pt  # Middle of the shoulders (Neck Base)
        neck_color = COLOR_BAD if metrics.neck_bad else COLOR_GOOD

        # Subtle cross-links between left and right landmarks showing the midpoint
        draw_dashed_line(frame, metrics.left_ear_pt, metrics.right_ear_pt, (120, 160, 220), thickness=1, dash_len=4)
        draw_dashed_line(frame, metrics.left_shoulder_pt, metrics.right_shoulder_pt, (120, 160, 220), thickness=1, dash_len=4)

        for side_pt in [metrics.left_ear_pt, metrics.right_ear_pt,
                        metrics.left_shoulder_pt, metrics.right_shoulder_pt]:
            cv2.circle(frame, side_pt, 3, (160, 160, 180), -1, cv2.LINE_AA)

        # Vertical plumb line straight up from Mid-Shoulder
        plumb_shoulder = (shoulder[0], max(0, shoulder[1] - 130))
        draw_dashed_line(frame, shoulder, plumb_shoulder, (220, 220, 220), thickness=1, dash_len=6)

        # Neck vector: Mid-Shoulder -> Mid-Ear
        cv2.line(frame, shoulder, ear, neck_color, 4, cv2.LINE_AA)

        # Central Landmark Nodes
        for pt, label in [(shoulder, "Mid-Shoulder"), (ear, "Mid-Ear")]:
            cv2.circle(frame, pt, 9, (255, 255, 255), -1, cv2.LINE_AA)
            cv2.circle(frame, pt, 6, (30, 30, 30), -1, cv2.LINE_AA)

        # Angle text tag near ear
        cv2.putText(frame, f"Neck: {metrics.neck_angle:.1f} deg",
                    (ear[0] + 12, ear[1] + 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.52, neck_color, 2, cv2.LINE_AA)

    # 2. Top Banner Status Box
    banner_h = 56
    cv2.rectangle(overlay, (0, 0), (w, banner_h), COLOR_BG, -1)

    if state == "AWAITING_CORRECTION":
        banner_bg = COLOR_BAD
        vol_pct = min(100, warning_level * 25)
        banner_txt = f"WARNING [L{warning_level} - VOL {vol_pct}%]: STRAIGHTEN YOUR NECK! (CHECKING...)"
    elif state == "JUST_CORRECTED":
        banner_bg = COLOR_GOOD
        banner_txt = "NECK POSTURE RESTORED! GREAT JOB!"
    elif metrics.is_detected:
        if not metrics.neck_bad:
            banner_bg = (35, 120, 40)
            banner_txt = "NECK POSTURE: GOOD (Aligned)"
        else:
            banner_bg = COLOR_WARN
            banner_txt = f"FORWARD HEAD POSTURE DETECTED ({metrics.neck_angle:.1f} deg)"
    else:
        banner_bg = (50, 50, 60)
        banner_txt = "NO PERSON DETECTED - SIT IN SIDE VIEW OF CAMERA"

    cv2.rectangle(overlay, (0, 0), (w, banner_h), banner_bg, -1)
    cv2.putText(overlay, banner_txt, (20, 38),
                cv2.FONT_HERSHEY_SIMPLEX, 0.72, COLOR_WHITE, 2, cv2.LINE_AA)

    # 3. Left Metrics Card
    card_w, card_h = 300, 180
    card_x, card_y = 15, banner_h + 15
    cv2.rectangle(overlay, (card_x, card_y), (card_x + card_w, card_y + card_h), COLOR_BG, -1)
    cv2.rectangle(overlay, (card_x, card_y), (card_x + card_w, card_y + card_h), (70, 70, 80), 1)

    cv2.putText(overlay, "NECK POSTURE MONITOR", (card_x + 12, card_y + 24),
                cv2.FONT_HERSHEY_SIMPLEX, 0.52, (200, 200, 220), 1, cv2.LINE_AA)
    cv2.putText(overlay, "(Ref: Mid-Shoulder -> Mid-Ear)", (card_x + 12, card_y + 42),
                cv2.FONT_HERSHEY_SIMPLEX, 0.40, (140, 180, 240), 1, cv2.LINE_AA)

    side_text = f"Side Tracked: {metrics.side}" if metrics.is_detected else "Side: Searching..."
    cv2.putText(overlay, side_text, (card_x + 12, card_y + 64),
                cv2.FONT_HERSHEY_SIMPLEX, 0.48, COLOR_WHITE, 1, cv2.LINE_AA)

    neck_c = COLOR_BAD if metrics.neck_bad else COLOR_GOOD
    neck_status = "SLOUCH" if metrics.neck_bad else "OK"
    cv2.putText(overlay, f"Neck Angle: {metrics.neck_angle:4.1f} deg  [{neck_status}]",
                (card_x + 12, card_y + 92),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, neck_c, 2 if metrics.neck_bad else 1, cv2.LINE_AA)
    cv2.putText(overlay, f" (Threshold: max {analyzer.neck_threshold:.1f} deg)",
                (card_x + 12, card_y + 110),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, COLOR_MUTED, 1, cv2.LINE_AA)

    vol_text = f"Warning Escalation: Level {warning_level} ({min(100, warning_level*25)}% Vol)"
    vol_c = COLOR_BAD if warning_level >= 3 else (COLOR_WARN if warning_level == 2 else (180, 220, 180))
    cv2.putText(overlay, vol_text, (card_x + 12, card_y + 138),
                cv2.FONT_HERSHEY_SIMPLEX, 0.44, vol_c, 1, cv2.LINE_AA)

    calib_str = "Baseline: CALIBRATED (C)" if analyzer.is_calibrated else "Baseline: DEFAULT 12.0° (C to set)"
    cv2.putText(overlay, calib_str, (card_x + 12, card_y + 162),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, (150, 220, 255) if analyzer.is_calibrated else COLOR_MUTED, 1, cv2.LINE_AA)

    # 4. 5-Second Evaluation Progress Bar
    bar_w = 300
    bar_h = 10
    bar_x = card_x
    bar_y = card_y + card_h + 12

    progress = max(0.0, min(1.0, 1.0 - (time_until_check / check_interval)))
    cv2.rectangle(overlay, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), (50, 50, 60), -1)
    fill_w = int(bar_w * progress)
    bar_color = COLOR_WARN if time_until_check < 1.0 else (80, 180, 240)
    cv2.rectangle(overlay, (bar_x, bar_y), (bar_x + fill_w, bar_y + bar_h), bar_color, -1)

    cv2.putText(overlay, f"Next 5s Evaluation: {time_until_check:.1f}s",
                (bar_x, bar_y + bar_h + 18),
                cv2.FONT_HERSHEY_SIMPLEX, 0.46, (220, 220, 220), 1, cv2.LINE_AA)

    # 5. Bottom Controls Bar
    cv2.rectangle(overlay, (0, h - 30), (w, h), COLOR_BG, -1)
    sound_status = "ON" if sound_enabled else "OFF"
    controls = f"[C] Calibrate  |  [R] Reset (12.0°)  |  [M] Sound: {sound_status}  |  [Q] Exit"
    cv2.putText(overlay, controls, (20, h - 9),
                cv2.FONT_HERSHEY_SIMPLEX, 0.46, (190, 190, 200), 1, cv2.LINE_AA)

    cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)

# --- Main Video Feed & Posture Loop ---
def start_neck_monitor(camera_index=0, check_interval=5.0):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    model_path = ensure_model_file(base_dir)

    # Initialize single lightweight MediaPipe PoseLandmarker
    pose_options = vision.PoseLandmarkerOptions(
        base_options=python.BaseOptions(model_asset_path=model_path),
        running_mode=vision.RunningMode.IMAGE,
        min_pose_detection_confidence=0.5,
        min_pose_presence_confidence=0.5,
        min_tracking_confidence=0.5,
        output_segmentation_masks=False
    )
    pose_landmarker = vision.PoseLandmarker.create_from_options(pose_options)

    # Initialize Neck-Only Posture Analyzer (Default: 12.0°)
    analyzer = NeckPostureAnalyzer(neck_threshold=12.0)

    # Start external pop-up controller (runs in separate process, 0 GUI lag)
    popup = PopupController()

    # Open Camera feed (CAP_DSHOW for fast Windows startup)
    cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap = cv2.VideoCapture(camera_index)

    if not cap.isOpened():
        print(f"Error: Could not open camera at index {camera_index}.")
        popup.close()
        sys.exit(1)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    print("==================================================")
    print("   Lightweight Neck Posture Guardian Active       ")
    print("==================================================")
    print(f"-> Camera feed opened on index {camera_index}")
    print(f"-> Model: {os.path.basename(model_path)} (Optimized for speed)")
    print(f"-> Evaluation Interval: {check_interval:.1f} seconds")
    print(f"-> Neck Threshold: max {analyzer.neck_threshold:.1f} degrees")
    print("-> Mode: PURE NECK COMPARISON (Mid-Shoulder -> Mid-Ear)")
    print("-> Controls: [C] Calibrate | [R] Reset | [M] Mute | [Q] Exit")
    print("==================================================")

    last_check_time = time.time()
    state = "NORMAL"
    good_streak_start = None
    corrected_banner_expiry = 0.0
    sound_enabled = True
    consecutive_bad_checks = 0

    recent_neck_angles = deque(maxlen=6)

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("Error: Failed to grab frame from camera.")
                break

            h, w, _ = frame.shape
            current_time = time.time()

            # Convert BGR frame to RGB for MediaPipe
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

            # Single pose inference
            detection_result = pose_landmarker.detect(mp_image)
            landmarks = detection_result.pose_landmarks[0] if detection_result.pose_landmarks else None
            metrics = analyzer.analyze(landmarks, w, h)

            # Smooth angle over rolling window to eliminate any camera jitter
            if metrics.is_detected:
                recent_neck_angles.append(metrics.neck_angle)
                avg_neck = sum(recent_neck_angles) / len(recent_neck_angles)
                metrics.neck_angle = avg_neck
                metrics.neck_bad = avg_neck > analyzer.neck_threshold

            if state == "JUST_CORRECTED" and current_time > corrected_banner_expiry:
                state = "NORMAL"

            # -------------------------------------------------------------
            # Continuous OpenCV Verification:
            # "the openCV must then check whether my posture is good or not"
            # -------------------------------------------------------------
            if state == "AWAITING_CORRECTION":
                if metrics.is_detected and not metrics.neck_bad:
                    if good_streak_start is None:
                        good_streak_start = current_time
                    elif current_time - good_streak_start >= 1.0:
                        # User officially straightened neck!
                        consecutive_bad_checks = 0
                        print(f"[{time.strftime('%H:%M:%S')}] OpenCV Check: Neck posture restored! ({metrics.neck_angle:.1f}°)")
                        popup.trigger_corrected(metrics.neck_angle)
                        play_success_sound(sound_enabled)
                        state = "JUST_CORRECTED"
                        corrected_banner_expiry = current_time + 3.0
                        good_streak_start = None
                        last_check_time = current_time
                else:
                    good_streak_start = None

            # -------------------------------------------------------------
            # Periodic 5-Second Interval Posture Check:
            # "make it analyze the frame every 5 seconds and create a pop up"
            # -------------------------------------------------------------
            time_until_check = max(0.0, check_interval - (current_time - last_check_time))

            if (current_time - last_check_time) >= check_interval:
                last_check_time = current_time

                if metrics.is_detected:
                    if metrics.neck_bad:
                        consecutive_bad_checks += 1
                        warning_level = min(4, consecutive_bad_checks)
                        state = "AWAITING_CORRECTION"
                        good_streak_start = None

                        vol_pct = min(100, warning_level * 25)
                        print(f"[{time.strftime('%H:%M:%S')}] 5s Check ALERT [Level {warning_level} - Vol {vol_pct}%]: Straighten your NECK! ({metrics.neck_angle:.1f}°)")
                        popup.trigger_alert(metrics.neck_angle, warning_level=warning_level)
                        play_progressive_warning(warning_level, sound_enabled)
                    else:
                        consecutive_bad_checks = 0
                        print(f"[{time.strftime('%H:%M:%S')}] 5s Check: Neck posture is GOOD ({metrics.neck_angle:.1f}°)")

            curr_display_level = max(1, min(4, consecutive_bad_checks))

            # Render lightweight HUD
            draw_hud(frame, metrics, analyzer, time_until_check, check_interval,
                     state, sound_enabled, warning_level=curr_display_level)

            # Display video window
            cv2.imshow("Neck Posture Guardian (Press Q to quit)", frame)

            # Keyboard Input
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == 27:
                print("Exiting neck posture monitor...")
                break
            elif key == ord('c'):
                if metrics.is_detected:
                    analyzer.calibrate(metrics.neck_angle)
                    print(f"[Calibrated] Upright baseline: {analyzer.baseline_neck:.1f}° | New Neck Threshold: {analyzer.neck_threshold:.1f}°")
                else:
                    print("[Calibration Failed] Please ensure you are visible in the side view before calibrating.")
            elif key == ord('r'):
                analyzer.reset_calibration(default_neck=12.0)
                consecutive_bad_checks = 0
                print("[Reset] Restored default neck threshold: 12.0°")
            elif key == ord('m'):
                sound_enabled = not sound_enabled
                print(f"[Audio] Sound alert is now {'ENABLED' if sound_enabled else 'MUTED'}")

    finally:
        cap.release()
        cv2.destroyAllWindows()
        pose_landmarker.close()
        popup.close()
        print("Neck Posture Guardian stopped successfully.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Lightweight side-view neck posture analyzer with 5-second checks and pop-up warnings.")
    parser.add_argument("--camera", type=int, default=0, help="Camera index (default: 0)")
    parser.add_argument("--interval", type=float, default=5.0, help="Analysis check interval in seconds (default: 5.0)")
    args = parser.parse_args()

    start_neck_monitor(camera_index=args.camera, check_interval=args.interval)
