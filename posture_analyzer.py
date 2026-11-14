import math
import numpy as np

class PostureMetrics:
    def __init__(self):
        self.is_detected = False
        self.side = "UNKNOWN"
        self.neck_angle = 0.0
        self.back_angle = 0.0
        self.neck_bad = False
        self.back_bad = False
        self.target = "NONE"  # "NONE", "NECK", "BACK", "BOTH"
        
        # Primary Midline Reference Points
        self.ear_pt = (0, 0)       # Middle of the ears (Head Center)
        self.shoulder_pt = (0, 0)  # Middle of the shoulders (C7 Neck Base)
        self.hip_pt = (0, 0)       # Middle of the hips (Pelvis Base)

        # Individual Joint Points for visual reference
        self.left_ear_pt = (0, 0)
        self.right_ear_pt = (0, 0)
        self.left_shoulder_pt = (0, 0)
        self.right_shoulder_pt = (0, 0)
        self.left_hip_pt = (0, 0)
        self.right_hip_pt = (0, 0)

        self.confidence = 0.0

class SidePostureAnalyzer:
    def __init__(self, neck_threshold=12.0, back_threshold=20.0):
        self.neck_threshold = float(neck_threshold)
        self.back_threshold = float(back_threshold)
        self.baseline_neck = 0.0
        self.baseline_back = 0.0
        self.is_calibrated = False

    def calibrate(self, neck_angle, back_angle):
        """Calibrate using user's upright posture baseline, capped at 12.0° max neck threshold."""
        self.baseline_neck = neck_angle
        self.baseline_back = back_angle
        # Cap neck threshold strictly at 12.0 degrees
        self.neck_threshold = min(12.0, max(6.0, neck_angle + 4.0))
        self.back_threshold = max(14.0, back_angle + 8.0)
        self.is_calibrated = True

    def reset_calibration(self, default_neck=12.0, default_back=20.0):
        self.neck_threshold = float(default_neck)
        self.back_threshold = float(default_back)
        self.baseline_neck = 0.0
        self.baseline_back = 0.0
        self.is_calibrated = False

    def analyze(self, landmarks, frame_w, frame_h):
        metrics = PostureMetrics()
        if not landmarks or len(landmarks) < 25:
            return metrics

        # MediaPipe Landmark IDs:
        # Left side: Ear=7, Shoulder=11, Hip=23
        # Right side: Ear=8, Shoulder=12, Hip=24
        left_ear = landmarks[7]
        left_shoulder = landmarks[11]
        left_hip = landmarks[23]

        right_ear = landmarks[8]
        right_shoulder = landmarks[12]
        right_hip = landmarks[24]

        # Visibility scores
        l_ear_v = getattr(left_ear, 'visibility', 0.5)
        r_ear_v = getattr(right_ear, 'visibility', 0.5)
        l_sh_v = getattr(left_shoulder, 'visibility', 0.5)
        r_sh_v = getattr(right_shoulder, 'visibility', 0.5)
        l_hip_v = getattr(left_hip, 'visibility', 0.5)
        r_hip_v = getattr(right_hip, 'visibility', 0.5)

        left_vis = (l_ear_v + l_sh_v + l_hip_v) / 3.0
        right_vis = (r_ear_v + r_sh_v + r_hip_v) / 3.0
        total_conf = max(left_vis, right_vis)

        if total_conf < 0.25:
            metrics.is_detected = False
            return metrics

        side = "LEFT" if left_vis >= right_vis else "RIGHT"

        # -------------------------------------------------------------
        # Compute Middle of the Ear, Middle of the Shoulder, Middle of the Hip
        # -------------------------------------------------------------
        # Confidence-weighted midpoints ensure stability even if one side is partially occluded
        w_l_ear = max(0.1, l_ear_v)
        w_r_ear = max(0.1, r_ear_v)
        mid_ear_x = (left_ear.x * w_l_ear + right_ear.x * w_r_ear) / (w_l_ear + w_r_ear)
        mid_ear_y = (left_ear.y * w_l_ear + right_ear.y * w_r_ear) / (w_l_ear + w_r_ear)

        w_l_sh = max(0.1, l_sh_v)
        w_r_sh = max(0.1, r_sh_v)
        mid_sh_x = (left_shoulder.x * w_l_sh + right_shoulder.x * w_r_sh) / (w_l_sh + w_r_sh)
        mid_sh_y = (left_shoulder.y * w_l_sh + right_shoulder.y * w_r_sh) / (w_l_sh + w_r_sh)

        w_l_hip = max(0.1, l_hip_v)
        w_r_hip = max(0.1, r_hip_v)
        mid_hip_x = (left_hip.x * w_l_hip + right_hip.x * w_r_hip) / (w_l_hip + w_r_hip)
        mid_hip_y = (left_hip.y * w_l_hip + right_hip.y * w_r_hip) / (w_l_hip + w_r_hip)

        # Convert to screen pixel coordinates
        ear_pt = (int(mid_ear_x * frame_w), int(mid_ear_y * frame_h))
        shoulder_pt = (int(mid_sh_x * frame_w), int(mid_sh_y * frame_h))
        hip_pt = (int(mid_hip_x * frame_w), int(mid_hip_y * frame_h))

        # Individual points for visual overlay
        l_ear_pt = (int(left_ear.x * frame_w), int(left_ear.y * frame_h))
        r_ear_pt = (int(right_ear.x * frame_w), int(right_ear.y * frame_h))
        l_sh_pt = (int(left_shoulder.x * frame_w), int(left_shoulder.y * frame_h))
        r_sh_pt = (int(right_shoulder.x * frame_w), int(right_shoulder.y * frame_h))
        l_hip_pt = (int(left_hip.x * frame_w), int(left_hip.y * frame_h))
        r_hip_pt = (int(right_hip.x * frame_w), int(right_hip.y * frame_h))

        # -------------------------------------------------------------
        # Posture Reference: Middle of Shoulder to Middle of Ear
        # -------------------------------------------------------------
        # Vector from middle of shoulder to middle of ear
        dx_neck = abs(ear_pt[0] - shoulder_pt[0])
        dy_neck = max(1.0, float(shoulder_pt[1] - ear_pt[1]))
        neck_angle = math.degrees(math.atan2(dx_neck, dy_neck))

        # Back / Torso Angle: Middle of Hip to Middle of Shoulder
        dx_back = abs(shoulder_pt[0] - hip_pt[0])
        dy_back = max(1.0, float(hip_pt[1] - shoulder_pt[1]))
        back_angle = math.degrees(math.atan2(dx_back, dy_back))

        # Evaluate against thresholds
        neck_bad = neck_angle > self.neck_threshold
        back_bad = back_angle > self.back_threshold

        if neck_bad and back_bad:
            target = "BOTH"
        elif neck_bad:
            target = "NECK"
        elif back_bad:
            target = "BACK"
        else:
            target = "NONE"

        metrics.is_detected = True
        metrics.side = side
        metrics.neck_angle = neck_angle
        metrics.back_angle = back_angle
        metrics.neck_bad = neck_bad
        metrics.back_bad = back_bad
        metrics.target = target

        # Primary reference landmarks
        metrics.ear_pt = ear_pt
        metrics.shoulder_pt = shoulder_pt
        metrics.hip_pt = hip_pt

        # Joint details
        metrics.left_ear_pt = l_ear_pt
        metrics.right_ear_pt = r_ear_pt
        metrics.left_shoulder_pt = l_sh_pt
        metrics.right_shoulder_pt = r_sh_pt
        metrics.left_hip_pt = l_hip_pt
        metrics.right_hip_pt = r_hip_pt

        metrics.confidence = total_conf

        return metrics
