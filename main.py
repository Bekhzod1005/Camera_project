import os
import sys
import time
import math
import json
import argparse
import threading
import subprocess
from collections import deque
import cv2
import numpy as np

# Avoid matplotlib cache folder permission warnings on Windows
os.environ["MPLCONFIGDIR"] = os.environ.get("TEMP", ".")

import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from posture_analyzer import SidePostureAnalyzer
from gesture_detector import MiddleFingerDetector
from sound_effects import (
    play_progressive_warning,
    play_success_sound,
    play_voice_fuck_you_issa,
    get_discord_virtual_devices
)

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

    def trigger_alert(self, target, neck_angle, back_angle, warning_level=1, tip=""):
        self.send({
            "action": "ALERT",
            "target": target,
            "neck_angle": float(neck_angle),
            "back_angle": float(back_angle),
            "warning_level": int(warning_level),
            "tip": tip
        })

    def trigger_corrected(self, neck_angle, back_angle):
        self.send({
            "action": "CORRECTED",
            "neck_angle": float(neck_angle),
            "back_angle": float(back_angle)
        })

    def trigger_middle_finger(self):
        self.send({"action": "MIDDLE_FINGER"})

    def dismiss_middle_finger(self):
        self.send({"action": "MIDDLE_FINGER_DISMISS"})

    def close(self):
        if self.process and self.process.poll() is None:
            try:
                self.send({"action": "QUIT"})
                self.process.terminate()
            except Exception:
                pass


# --- Visual HUD Drawing Functions ---
def draw_dashed_line(img, pt1, pt2, color, thickness=1, dash_len=8):
    """Draw a dashed line between two points."""
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

HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),        # Thumb
    (0, 5), (5, 6), (6, 7), (7, 8),        # Index
    (5, 9), (9, 10), (10, 11), (11, 12),   # Middle
    (9, 13), (13, 14), (14, 15), (15, 16), # Ring
    (13, 17), (17, 18), (18, 19), (19, 20),# Pinky
    (0, 17)                                # Palm base
]

def draw_hands(frame, hand_landmarks_list, is_middle_finger):
    h, w, _ = frame.shape
    line_color = (40, 40, 240) if is_middle_finger else (0, 220, 255)
    point_color = (255, 255, 255)

    for lms in hand_landmarks_list:
        pts = [(int(p.x * w), int(p.y * h)) for p in lms]
        for start_idx, end_idx in HAND_CONNECTIONS:
            cv2.line(frame, pts[start_idx], pts[end_idx], line_color, 2, cv2.LINE_AA)
        for pt in pts:
            cv2.circle(frame, pt, 4, point_color, -1, cv2.LINE_AA)

def draw_middle_finger_overlay(frame):
    """Draw a dramatic bold 'FUCK YOU ISSA' popup across the entire OpenCV frame."""
    h, w, _ = frame.shape
    overlay = frame.copy()

    # Dark translucent blood-red shade across the entire frame
    cv2.rectangle(overlay, (0, 0), (w, h), (15, 0, 80), -1)
    cv2.addWeighted(overlay, 0.72, frame, 0.28, 0, frame)

    text = "FUCK YOU ISSA"
    font = cv2.FONT_HERSHEY_DUPLEX
    font_scale = 3.2
    thickness = 8

    # Ensure font scale dynamically fits screen
    (tw, th), _ = cv2.getTextSize(text, font, font_scale, thickness)
    if tw > w * 0.90:
        font_scale = font_scale * (w * 0.88 / tw)
        (tw, th), _ = cv2.getTextSize(text, font, font_scale, thickness)

    tx = (w - tw) // 2
    ty = (h + th) // 2 - 20

    # Draw black drop-shadow
    cv2.putText(frame, text, (tx + 6, ty + 6), font, font_scale, (0, 0, 0), thickness + 6, cv2.LINE_AA)
    # Draw thick crimson border
    cv2.putText(frame, text, (tx, ty), font, font_scale, (20, 20, 190), thickness + 4, cv2.LINE_AA)
    # Draw pure white text
    cv2.putText(frame, text, (tx, ty), font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)

    # Subtitles
    sub1 = "[!] MIDDLE FINGER DETECTED - PLAYING AUDIO"
    (s1w, _), _ = cv2.getTextSize(sub1, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)
    cv2.putText(frame, sub1, ((w - s1w) // 2, ty - th - 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (80, 80, 255), 2, cv2.LINE_AA)

    sub2 = "Lower hand or press ESC to dismiss"
    (s2w, _), _ = cv2.getTextSize(sub2, cv2.FONT_HERSHEY_SIMPLEX, 0.65, 2)
    cv2.putText(frame, sub2, ((w - s2w) // 2, ty + 50),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, (200, 200, 200), 2, cv2.LINE_AA)

def draw_hud(frame, metrics, analyzer, time_until_check, check_interval,
             state, active_alert_target, alert_message, sound_enabled, warning_level=1):
    """Render rich, modern head-up display on top of the OpenCV camera frame."""
    h, w, _ = frame.shape
    overlay = frame.copy()

    COLOR_GOOD = (70, 200, 70)       # Green
    COLOR_WARN = (40, 160, 255)      # Orange
    COLOR_BAD = (40, 40, 240)        # Bright Red
    COLOR_MUTED = (160, 160, 160)    # Gray
    COLOR_BG = (25, 25, 30)          # Dark background
    COLOR_WHITE = (250, 250, 250)

    # 1. Draw Skeleton Alignment Lines (Referencing Mid-Shoulder to Mid-Ear)
    if metrics.is_detected:
        ear = metrics.ear_pt            # Middle of the ears (Head Center)
        shoulder = metrics.shoulder_pt  # Middle of the shoulders (Neck Base)
        hip = metrics.hip_pt            # Middle of the hips (Pelvis Base)

        neck_color = COLOR_BAD if metrics.neck_bad else COLOR_GOOD
        back_color = COLOR_BAD if metrics.back_bad else COLOR_GOOD

        # Subtle cross-links between left and right landmarks showing the midpoint
        draw_dashed_line(frame, metrics.left_ear_pt, metrics.right_ear_pt, (120, 160, 220), thickness=1, dash_len=4)
        draw_dashed_line(frame, metrics.left_shoulder_pt, metrics.right_shoulder_pt, (120, 160, 220), thickness=1, dash_len=4)
        draw_dashed_line(frame, metrics.left_hip_pt, metrics.right_hip_pt, (120, 160, 220), thickness=1, dash_len=4)

        # Small dots for individual left/right joints
        for side_pt in [metrics.left_ear_pt, metrics.right_ear_pt,
                        metrics.left_shoulder_pt, metrics.right_shoulder_pt,
                        metrics.left_hip_pt, metrics.right_hip_pt]:
            cv2.circle(frame, side_pt, 3, (160, 160, 180), -1, cv2.LINE_AA)

        # Vertical plumb reference lines straight up from Mid-Shoulder and Mid-Hip
        plumb_shoulder = (shoulder[0], max(0, shoulder[1] - 120))
        plumb_hip = (hip[0], max(0, hip[1] - 140))
        draw_dashed_line(frame, shoulder, plumb_shoulder, (220, 220, 220), thickness=1, dash_len=6)
        draw_dashed_line(frame, hip, plumb_hip, (220, 220, 220), thickness=1, dash_len=6)

        # Primary Posture Reference: Mid-Hip -> Mid-Shoulder and Mid-Shoulder -> Mid-Ear
        cv2.line(frame, hip, shoulder, back_color, 4, cv2.LINE_AA)
        cv2.line(frame, shoulder, ear, neck_color, 4, cv2.LINE_AA)

        # Prominent Central Landmark Nodes
        for pt, label in [(hip, "Mid-Hip"), (shoulder, "Mid-Shoulder"), (ear, "Mid-Ear")]:
            cv2.circle(frame, pt, 9, (255, 255, 255), -1, cv2.LINE_AA)
            cv2.circle(frame, pt, 6, (30, 30, 30), -1, cv2.LINE_AA)

        # Posture Tags
        cv2.putText(frame, f"Mid-Ear ({metrics.neck_angle:.1f} deg)",
                    (ear[0] + 12, ear[1] + 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.48, neck_color, 2, cv2.LINE_AA)
        cv2.putText(frame, f"Mid-Shoulder ({metrics.back_angle:.1f} deg)",
                    (shoulder[0] + 12, shoulder[1] + 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.48, back_color, 2, cv2.LINE_AA)

    # 2. Top Banner Status Box
    banner_h = 60
    cv2.rectangle(overlay, (0, 0), (w, banner_h), COLOR_BG, -1)

    if state == "AWAITING_CORRECTION":
        banner_bg = COLOR_BAD
        vol_pct = min(100, warning_level * 25)
        banner_txt = f"WARNING [L{warning_level} - VOL {vol_pct}%]: STRAIGHTEN {active_alert_target}! (CHECKING...)"
    elif state == "JUST_CORRECTED":
        banner_bg = COLOR_GOOD
        banner_txt = "POSTURE RESTORED! GREAT JOB!"
    elif metrics.is_detected:
        if metrics.target == "NONE":
            banner_bg = (35, 120, 40)
            banner_txt = "POSTURE HEALTHY (Neck & Back Aligned)"
        else:
            banner_bg = COLOR_WARN
            banner_txt = f"POOR POSTURE DETECTED: {metrics.target}"
    else:
        banner_bg = (50, 50, 60)
        banner_txt = "NO PERSON DETECTED - SIT IN SIDE VIEW OF CAMERA"

    cv2.rectangle(overlay, (0, 0), (w, banner_h), banner_bg, -1)
    cv2.putText(overlay, banner_txt, (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 0.72, COLOR_WHITE, 2, cv2.LINE_AA)

    # 3. Left Metrics & Angle Card
    card_w, card_h = 320, 210
    card_x, card_y = 15, banner_h + 15
    cv2.rectangle(overlay, (card_x, card_y), (card_x + card_w, card_y + card_h), COLOR_BG, -1)
    cv2.rectangle(overlay, (card_x, card_y), (card_x + card_w, card_y + card_h), (70, 70, 80), 1)

    cv2.putText(overlay, "SIDE POSTURE METRICS", (card_x + 12, card_y + 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.52, (200, 200, 220), 1, cv2.LINE_AA)
    cv2.putText(overlay, "(Ref: Mid-Shoulder -> Mid-Ear)", (card_x + 12, card_y + 38),
                cv2.FONT_HERSHEY_SIMPLEX, 0.40, (140, 180, 240), 1, cv2.LINE_AA)

    side_text = f"Side Tracked: {metrics.side}" if metrics.is_detected else "Side: Searching..."
    cv2.putText(overlay, side_text, (card_x + 12, card_y + 56),
                cv2.FONT_HERSHEY_SIMPLEX, 0.48, COLOR_WHITE, 1, cv2.LINE_AA)

    # Neck Metric
    neck_c = COLOR_BAD if metrics.neck_bad else COLOR_GOOD
    neck_status = "SLOUCH" if metrics.neck_bad else "OK"
    cv2.putText(overlay, f"Neck Angle: {metrics.neck_angle:4.1f} deg  [{neck_status}]",
                (card_x + 12, card_y + 76),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, neck_c, 2 if metrics.neck_bad else 1, cv2.LINE_AA)
    cv2.putText(overlay, f" (Threshold: max {analyzer.neck_threshold:.1f} deg)",
                (card_x + 12, card_y + 94),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, COLOR_MUTED, 1, cv2.LINE_AA)

    # Back Metric
    back_c = COLOR_BAD if metrics.back_bad else COLOR_GOOD
    back_status = "SLOUCH" if metrics.back_bad else "OK"
    cv2.putText(overlay, f"Back Angle: {metrics.back_angle:4.1f} deg  [{back_status}]",
                (card_x + 12, card_y + 122),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, back_c, 2 if metrics.back_bad else 1, cv2.LINE_AA)
    cv2.putText(overlay, f" (Threshold: max {analyzer.back_threshold:.1f} deg)",
                (card_x + 12, card_y + 140),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, COLOR_MUTED, 1, cv2.LINE_AA)

    # Progressive Volume Status
    vol_text = f"Warning Escalation: Level {warning_level} ({min(100, warning_level*25)}% Vol)"
    vol_c = COLOR_BAD if warning_level >= 3 else (COLOR_WARN if warning_level == 2 else (180, 220, 180))
    cv2.putText(overlay, vol_text, (card_x + 12, card_y + 168),
                cv2.FONT_HERSHEY_SIMPLEX, 0.44, vol_c, 1, cv2.LINE_AA)

    # Calibration status
    calib_str = "Baseline: CALIBRATED (C)" if analyzer.is_calibrated else "Baseline: DEFAULT (Press C)"
    cv2.putText(overlay, calib_str, (card_x + 12, card_y + 194),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, (150, 220, 255) if analyzer.is_calibrated else COLOR_MUTED, 1, cv2.LINE_AA)

    # 4. Bottom 5-Second Evaluation Progress Bar
    bar_w = 320
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

    # 5. Bottom Instructions Bar
    cv2.rectangle(overlay, (0, h - 32), (w, h), COLOR_BG, -1)
    sound_status = "ON" if sound_enabled else "OFF"
    controls = f"[C] Calibrate  |  [R] Reset  |  [M] Sound: {sound_status}  |  [Q] Exit"
    cv2.putText(overlay, controls, (20, h - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.46, (190, 190, 200), 1, cv2.LINE_AA)

    cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)


def ensure_model_files(base_dir):
    """Automatically download MediaPipe task models if missing."""
    import urllib.request
    models = {
        "pose_landmarker_full.task": "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/latest/pose_landmarker_full.task",
        "hand_landmarker.task": "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task"
    }
    for filename, url in models.items():
        filepath = os.path.join(base_dir, filename)
        if not os.path.exists(filepath):
            print(f"Downloading required model '{filename}'...")
            try:
                urllib.request.urlretrieve(url, filepath)
                print(f"Downloaded '{filename}' successfully.")
            except Exception as e:
                print(f"Failed to auto-download '{filename}': {e}")

# --- Main Video Feed & Posture Loop ---
def start_posture_monitor(camera_index=0, check_interval=5.0):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    ensure_model_files(base_dir)

    pose_model_path = os.path.join(base_dir, "pose_landmarker_full.task")
    hand_model_path = os.path.join(base_dir, "hand_landmarker.task")

    if not os.path.exists(pose_model_path):
        print(f"Error: Model file '{pose_model_path}' not found.")
        sys.exit(1)
    if not os.path.exists(hand_model_path):
        print(f"Error: Model file '{hand_model_path}' not found.")
        sys.exit(1)

    # Initialize MediaPipe PoseLandmarker
    pose_options = vision.PoseLandmarkerOptions(
        base_options=python.BaseOptions(model_asset_path=pose_model_path),
        running_mode=vision.RunningMode.IMAGE,
        min_pose_detection_confidence=0.5,
        min_pose_presence_confidence=0.5,
        min_tracking_confidence=0.5,
        output_segmentation_masks=False
    )
    pose_landmarker = vision.PoseLandmarker.create_from_options(pose_options)

    # Initialize MediaPipe HandLandmarker
    hand_options = vision.HandLandmarkerOptions(
        base_options=python.BaseOptions(model_asset_path=hand_model_path),
        running_mode=vision.RunningMode.IMAGE,
        num_hands=2,
        min_hand_detection_confidence=0.5,
        min_hand_presence_confidence=0.5,
        min_tracking_confidence=0.5
    )
    hand_landmarker = vision.HandLandmarker.create_from_options(hand_options)

    # Initialize Posture Analyzer & Middle Finger Detector (Neck: 12.0°, Back: 20.0°)
    analyzer = SidePostureAnalyzer(neck_threshold=12.0, back_threshold=20.0)
    gesture_detector = MiddleFingerDetector(debounce_frames=2)

    # Start external pop-up controller
    popup = PopupController()

    # Open Camera feed
    cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        print(f"Warning: DirectShow failed for camera {camera_index}, retrying default backend...")
        cap = cv2.VideoCapture(camera_index)

    if not cap.isOpened():
        print(f"Error: Could not open camera at index {camera_index}.")
        popup.close()
        sys.exit(1)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    v_devs = get_discord_virtual_devices()
    discord_status = f"Active on '{v_devs[0][1]}'" if v_devs else "Ready (Routes to virtual mic cable if installed)"

    print("==================================================")
    print("  Posture Guardian + 'FUCK YOU ISSA' Active      ")
    print("==================================================")
    print(f"-> Camera feed opened on index {camera_index}")
    print(f"-> Evaluation Interval: {check_interval:.1f} seconds")
    print(f"-> Neck Threshold: max {analyzer.neck_threshold:.1f} degrees")
    print(f"-> Back Threshold: max {analyzer.back_threshold:.1f} degrees")
    print(f"-> Discord Mic Broadcast: {discord_status}")
    print("-> Progressive audio: Warnings get louder the longer bad posture lasts")
    print("-> Gesture: Middle finger triggers 'FUCK YOU ISSA' fullscreen + mic voice")
    print("-> Controls: [C] Calibrate | [R] Reset | [M] Mute | [Q] Exit")
    print("==================================================")

    last_check_time = time.time()
    state = "NORMAL"
    active_alert_target = "NONE"
    alert_message = ""
    good_posture_streak_start = None
    corrected_banner_expiry = 0.0
    sound_enabled = True

    # Progressive warning level counter
    consecutive_bad_checks = 0

    # Middle finger tracking state
    middle_finger_active = False
    middle_finger_last_seen = 0.0

    recent_neck_angles = deque(maxlen=10)
    recent_back_angles = deque(maxlen=10)

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

            # 1. Detect Hands & Recognize Middle Finger Gesture
            hand_result = hand_landmarker.detect(mp_image)
            is_mf = gesture_detector.process_hands(hand_result.hand_landmarks)

            if is_mf:
                middle_finger_last_seen = current_time
                if not middle_finger_active:
                    middle_finger_active = True
                    print(f"[{time.strftime('%H:%M:%S')}] Gesture Alert: Middle finger detected! Triggering 'FUCK YOU ISSA' popup & voice audio.")
                    popup.trigger_middle_finger()
                    play_voice_fuck_you_issa(sound_enabled)
            else:
                # Require 1.5 seconds of no middle finger before dismissing fullscreen popup
                if middle_finger_active and (current_time - middle_finger_last_seen > 1.5):
                    middle_finger_active = False
                    popup.dismiss_middle_finger()

            # Draw Hand Landmarks
            if hand_result.hand_landmarks:
                draw_hands(frame, hand_result.hand_landmarks, middle_finger_active)

            # 2. Detect Body Pose & Analyze Posture
            detection_result = pose_landmarker.detect(mp_image)
            landmarks = detection_result.pose_landmarks[0] if detection_result.pose_landmarks else None
            metrics = analyzer.analyze(landmarks, w, h)

            # Smooth posture angles
            if metrics.is_detected:
                recent_neck_angles.append(metrics.neck_angle)
                recent_back_angles.append(metrics.back_angle)
                avg_neck = sum(recent_neck_angles) / len(recent_neck_angles)
                avg_back = sum(recent_back_angles) / len(recent_back_angles)
                metrics.neck_angle = avg_neck
                metrics.back_angle = avg_back
                metrics.neck_bad = avg_neck > analyzer.neck_threshold
                metrics.back_bad = avg_back > analyzer.back_threshold

                if metrics.neck_bad and metrics.back_bad:
                    metrics.target = "BOTH"
                elif metrics.neck_bad:
                    metrics.target = "NECK"
                elif metrics.back_bad:
                    metrics.target = "BACK"
                else:
                    metrics.target = "NONE"

            if state == "JUST_CORRECTED" and current_time > corrected_banner_expiry:
                state = "NORMAL"

            # 3. Posture Verification Mode
            if state == "AWAITING_CORRECTION":
                if metrics.is_detected and metrics.target == "NONE":
                    if good_posture_streak_start is None:
                        good_posture_streak_start = current_time
                    elif current_time - good_posture_streak_start >= 1.0:
                        # User corrected posture! Reset escalation counter & play success chime
                        consecutive_bad_checks = 0
                        print(f"[{time.strftime('%H:%M:%S')}] OpenCV Check: Posture corrected! Resetting alarm level. (Neck: {metrics.neck_angle:.1f}°, Back: {metrics.back_angle:.1f}°)")
                        popup.trigger_corrected(metrics.neck_angle, metrics.back_angle)
                        play_success_sound(sound_enabled)
                        state = "JUST_CORRECTED"
                        corrected_banner_expiry = current_time + 3.0
                        good_posture_streak_start = None
                        last_check_time = current_time
                else:
                    good_posture_streak_start = None

            # 4. Periodic 5-Second Interval Posture Check
            time_until_check = max(0.0, check_interval - (current_time - last_check_time))

            if (current_time - last_check_time) >= check_interval:
                last_check_time = current_time

                if metrics.is_detected:
                    if metrics.target != "NONE":
                        # Slouch detected: escalate warning level!
                        consecutive_bad_checks += 1
                        warning_level = min(4, consecutive_bad_checks)
                        active_alert_target = metrics.target
                        state = "AWAITING_CORRECTION"
                        good_posture_streak_start = None

                        tip = ""
                        if active_alert_target == "NECK":
                            tip = "Tuck your chin slightly and align ears vertically over shoulders."
                        elif active_alert_target == "BACK":
                            tip = "Engage your core, lift your chest, and pull your shoulders back."
                        elif active_alert_target == "BOTH":
                            tip = "Sit tall! Align your ears over shoulders and your torso over your hips."

                        vol_pct = min(100, warning_level * 25)
                        print(f"[{time.strftime('%H:%M:%S')}] 5s Check ALERT [Level {warning_level} - Vol {vol_pct}%]: Straighten {active_alert_target}! (Neck: {metrics.neck_angle:.1f}°, Back: {metrics.back_angle:.1f}°)")
                        popup.trigger_alert(active_alert_target, metrics.neck_angle, metrics.back_angle, warning_level=warning_level, tip=tip)
                        play_progressive_warning(warning_level, sound_enabled)
                    else:
                        consecutive_bad_checks = 0
                        print(f"[{time.strftime('%H:%M:%S')}] 5s Check: Posture is GOOD (Neck: {metrics.neck_angle:.1f}°, Back: {metrics.back_angle:.1f}°)")

            # Current warning level for display
            curr_display_level = max(1, min(4, consecutive_bad_checks))

            # Render standard HUD
            draw_hud(frame, metrics, analyzer, time_until_check, check_interval,
                     state, active_alert_target, alert_message, sound_enabled, warning_level=curr_display_level)

            # 5. Fullscreen Overlay across camera feed if middle finger is active
            if middle_finger_active:
                draw_middle_finger_overlay(frame)

            # Display video frame
            cv2.imshow("Posture Guardian - Side View (Press Q to quit)", frame)

            # Handle Keyboard Input
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == 27:
                print("Exiting posture monitor...")
                break
            elif key == ord('c'):
                if metrics.is_detected:
                    analyzer.calibrate(metrics.neck_angle, metrics.back_angle)
                    print(f"[Calibrated] Upright baseline: Neck={analyzer.baseline_neck:.1f}°, Back={analyzer.baseline_back:.1f}°")
                else:
                    print("[Calibration Failed] Please ensure you are visible in the side view before calibrating.")
            elif key == ord('r'):
                analyzer.reset_calibration()
                consecutive_bad_checks = 0
                print("[Reset] Restored default thresholds: Neck=12.0°, Back=20.0°")
            elif key == ord('m'):
                sound_enabled = not sound_enabled
                print(f"[Audio] Sound alert is now {'ENABLED' if sound_enabled else 'MUTED'}")

    finally:
        cap.release()
        cv2.destroyAllWindows()
        pose_landmarker.close()
        hand_landmarker.close()
        popup.close()
        print("Posture Guardian stopped successfully.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Side-view posture analyzer with progressive warnings and 'FUCK YOU ISSA' easter egg.")
    parser.add_argument("--camera", type=int, default=0, help="Camera index (default: 0)")
    parser.add_argument("--interval", type=float, default=5.0, help="Analysis check interval in seconds (default: 5.0)")
    args = parser.parse_args()

    start_posture_monitor(camera_index=args.camera, check_interval=args.interval)
