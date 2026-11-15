import math

class NeckMetrics:
    def __init__(self):
        self.is_detected = False
        self.side = "UNKNOWN"
        self.neck_angle = 0.0
        self.neck_bad = False

        # Primary Midline Reference Points
        self.ear_pt = (0, 0)       # Middle of the ears (Head Center)
        self.shoulder_pt = (0, 0)  # Middle of the shoulders (Neck Base)

        # Individual Joint Points for visual reference
        self.left_ear_pt = (0, 0)
        self.right_ear_pt = (0, 0)
        self.left_shoulder_pt = (0, 0)
        self.right_shoulder_pt = (0, 0)

        self.confidence = 0.0

class NeckPostureAnalyzer:
    """
    Lightweight, highly reliable neck-only posture analyzer.
    Compares the middle of the shoulder to the middle of the ear against a vertical plumb line.
    """
    def __init__(self, neck_threshold=12.0):
        self.neck_threshold = float(neck_threshold)
        self.baseline_neck = 0.0
        self.is_calibrated = False

    def calibrate(self, neck_angle):
        """Calibrate using user's upright posture baseline, capped at 15.0° max."""
        self.baseline_neck = float(neck_angle)
        # Adaptive threshold: baseline + 4°, capped strictly between 6.0° and 15.0°
        self.neck_threshold = min(15.0, max(6.0, neck_angle + 4.0))
        self.is_calibrated = True

    def reset_calibration(self, default_neck=12.0):
        self.neck_threshold = float(default_neck)
        self.baseline_neck = 0.0
        self.is_calibrated = False

    def analyze(self, landmarks, frame_w, frame_h):
        metrics = NeckMetrics()
        if not landmarks or len(landmarks) < 13:
            return metrics

        # MediaPipe Landmark IDs:
        # Left side: Ear=7, Shoulder=11
        # Right side: Ear=8, Shoulder=12
        left_ear = landmarks[7]
        left_shoulder = landmarks[11]
        right_ear = landmarks[8]
        right_shoulder = landmarks[12]

        l_ear_v = getattr(left_ear, 'visibility', 0.5)
        r_ear_v = getattr(right_ear, 'visibility', 0.5)
        l_sh_v = getattr(left_shoulder, 'visibility', 0.5)
        r_sh_v = getattr(right_shoulder, 'visibility', 0.5)

        left_vis = (l_ear_v + l_sh_v) / 2.0
        right_vis = (r_ear_v + r_sh_v) / 2.0
        total_conf = max(left_vis, right_vis)

        # Minimum visibility to prevent bogus false positives
        if total_conf < 0.25:
            metrics.is_detected = False
            return metrics

        side = "LEFT" if left_vis >= right_vis else "RIGHT"

        # Compute Middle of the Ear & Middle of the Shoulder
        w_l_ear = max(0.1, l_ear_v)
        w_r_ear = max(0.1, r_ear_v)
        mid_ear_x = (left_ear.x * w_l_ear + right_ear.x * w_r_ear) / (w_l_ear + w_r_ear)
        mid_ear_y = (left_ear.y * w_l_ear + right_ear.y * w_r_ear) / (w_l_ear + w_r_ear)

        w_l_sh = max(0.1, l_sh_v)
        w_r_sh = max(0.1, r_sh_v)
        mid_sh_x = (left_shoulder.x * w_l_sh + right_shoulder.x * w_r_sh) / (w_l_sh + w_r_sh)
        mid_sh_y = (left_shoulder.y * w_l_sh + right_shoulder.y * w_r_sh) / (w_l_sh + w_r_sh)

        # Convert to screen pixel coordinates
        ear_pt = (int(mid_ear_x * frame_w), int(mid_ear_y * frame_h))
        shoulder_pt = (int(mid_sh_x * frame_w), int(mid_sh_y * frame_h))

        # Individual points for visual overlay
        l_ear_pt = (int(left_ear.x * frame_w), int(left_ear.y * frame_h))
        r_ear_pt = (int(right_ear.x * frame_w), int(right_ear.y * frame_h))
        l_sh_pt = (int(left_shoulder.x * frame_w), int(left_shoulder.y * frame_h))
        r_sh_pt = (int(right_shoulder.x * frame_w), int(right_shoulder.y * frame_h))

        # Neck Angle: Middle of Shoulder to Middle of Ear vs Vertical Plumb Line
        dx_neck = abs(ear_pt[0] - shoulder_pt[0])
        dy_neck = max(1.0, float(shoulder_pt[1] - ear_pt[1]))
        neck_angle = math.degrees(math.atan2(dx_neck, dy_neck))

        metrics.is_detected = True
        metrics.side = side
        metrics.neck_angle = neck_angle
        metrics.neck_bad = neck_angle > self.neck_threshold
        metrics.ear_pt = ear_pt
        metrics.shoulder_pt = shoulder_pt
        metrics.left_ear_pt = l_ear_pt
        metrics.right_ear_pt = r_ear_pt
        metrics.left_shoulder_pt = l_sh_pt
        metrics.right_shoulder_pt = r_sh_pt
        metrics.confidence = total_conf

        return metrics
