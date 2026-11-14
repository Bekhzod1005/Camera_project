import math

class MiddleFingerDetector:
    def __init__(self, debounce_frames=2):
        self.consecutive_count = 0
        self.debounce_frames = debounce_frames
        self.is_active = False

    @staticmethod
    def _dist(p1, p2):
        return math.hypot(p1.x - p2.x, p1.y - p2.y)

    def check_hand(self, lms):
        """
        Evaluate if a single hand's 21 landmarks represent an extended middle finger
        with index, ring, and pinky folded.
        """
        if not lms or len(lms) < 21:
            return False

        wrist = lms[0]
        thumb_tip = lms[4]
        index_tip = lms[8]
        index_pip = lms[6]
        index_mcp = lms[5]

        mid_tip = lms[12]
        mid_pip = lms[10]
        mid_mcp = lms[9]

        ring_tip = lms[16]
        ring_pip = lms[14]
        ring_mcp = lms[13]

        pinky_tip = lms[20]
        pinky_pip = lms[18]
        pinky_mcp = lms[17]

        d_wrist_mid = self._dist(wrist, mid_tip)
        d_wrist_index = self._dist(wrist, index_tip)
        d_wrist_ring = self._dist(wrist, ring_tip)
        d_wrist_pinky = self._dist(wrist, pinky_tip)
        d_wrist_thumb = self._dist(wrist, thumb_tip)
        d_wrist_mid_pip = self._dist(wrist, mid_pip)

        # 1. Hand size threshold: discard tiny false detections
        if d_wrist_mid < 0.08:
            return False

        # 2. Middle finger must be fully extended:
        # Middle tip must be substantially further from wrist than middle PIP
        if d_wrist_mid <= d_wrist_mid_pip * 1.15:
            return False

        # 3. Middle finger dominance:
        # Distance from wrist to middle tip must clearly exceed distance to index, ring, and pinky tips
        if d_wrist_mid < d_wrist_index * 1.25:
            return False
        if d_wrist_mid < d_wrist_ring * 1.25:
            return False
        if d_wrist_mid < d_wrist_pinky * 1.25:
            return False

        # 4. Curled finger validation:
        # Non-middle fingers must be curled/folded inward
        index_folded = (
            self._dist(index_tip, index_mcp) < self._dist(index_pip, index_mcp) * 1.45
            or d_wrist_index < d_wrist_mid * 0.72
        )
        ring_folded = (
            self._dist(ring_tip, ring_mcp) < self._dist(ring_pip, ring_mcp) * 1.45
            or d_wrist_ring < d_wrist_mid * 0.72
        )
        pinky_folded = (
            self._dist(pinky_tip, pinky_mcp) < self._dist(pinky_pip, pinky_mcp) * 1.45
            or d_wrist_pinky < d_wrist_mid * 0.72
        )

        if not (index_folded and ring_folded and pinky_folded):
            return False

        # 5. Thumb must not be pointing straight out like an open palm
        if d_wrist_thumb > d_wrist_mid * 0.90:
            return False

        return True

    def process_hands(self, hand_landmarks_list):
        """
        Check all detected hands in the frame.
        Returns True if at least one hand is showing a middle finger.
        """
        raw_detected = False
        if hand_landmarks_list:
            for lms in hand_landmarks_list:
                if self.check_hand(lms):
                    raw_detected = True
                    break

        if raw_detected:
            self.consecutive_count += 1
            if self.consecutive_count >= self.debounce_frames:
                self.is_active = True
        else:
            self.consecutive_count = max(0, self.consecutive_count - 1)
            if self.consecutive_count == 0:
                self.is_active = False

        return self.is_active
