# Lightweight AI Neck Posture Guardian

A lightweight, highly reliable, real-time neck posture analysis system powered by OpenCV and MediaPipe Pose Lite. It monitors your head and neck alignment from a side-view camera, evaluates your posture every 5 seconds, and triggers an intelligent desktop pop-up warning you to straighten your **Neck**. OpenCV continuously monitors your posture after a warning and auto-dismisses the alert as soon as your neck alignment returns to a healthy position.

---

## Key Highlights

- **Pure Neck Comparison Only (No Back/Hip Overhead)**:
  - Focused strictly on cervical alignment: compares the **middle of the shoulders** to the **middle of the ears** against a vertical plumb line.
  - Forward head posture ("Text Neck") exceeding **12.0 degrees** triggers an alert.
- **Ultra-Lightweight & Fast**:
  - Uses the optimized `pose_landmarker_lite.task` model (~5.5 MB) for minimal CPU and RAM usage at high framerates (60+ FPS).
  - All Easter eggs and secondary hand models have been removed for maximum speed and simplicity.
- **5-Second Assessment Cycle**:
  - Evaluates posture every 5 seconds.
  - HUD displays a smooth countdown timer bar to the next evaluation.
- **Progressive Alert System**:
  - Alerts escalate in volume if bad neck posture persists:
    - **Level 1 (5s)**: Gentle single chime at **25% volume**.
    - **Level 2 (10s)**: Double alert chime at **50% volume**.
    - **Level 3 (15s)**: Urgent triple chime at **75% volume**.
    - **Level 4+ (20s+)**: Maximum intensity alarm at **100% volume**.
- **Continuous OpenCV Verification**:
  - After an alert, OpenCV tracks every frame. When you straighten your neck, the HUD turns green (`NECK POSTURE RESTORED!`), plays a pleasant confirmation chime, and auto-dismisses the pop-up.
- **One-Key Upright Calibration**:
  - Press `[C]` while sitting upright in your ideal posture to set a personalized baseline.
  - Press `[R]` to reset back to the default 12.0° threshold.

---

## Posture Reference: Mid-Shoulder to Mid-Ear

- **Middle of the Ears (`Mid-Ear`)**: The exact midpoint between your left ear tragus and right ear tragus (the head/skull pivot axis).
- **Middle of the Shoulders (`Mid-Shoulder`)**: The exact midpoint between your left acromion and right acromion (the base of the neck / C7 cervicothoracic junction).
- **Neck Angle ($\theta_{\text{neck}}$)**:
  $$\theta_{\text{neck}} = \arctan2\left(|\text{Mid-Ear}_x - \text{Mid-Shoulder}_x|, \text{Mid-Shoulder}_y - \text{Mid-Ear}_y\right) \times \frac{180}{\pi}$$

---

## Project Structure

```
opencv-usb-camera/
├── main.py                     # Main application entry point & OpenCV video loop
├── posture_analyzer.py         # Lightweight Mid-Shoulder -> Mid-Ear neck analyzer
├── posture_popup.py            # Non-blocking Tkinter desktop neck warning pop-up
├── sound_effects.py            # In-memory progressive volume audio chimes
├── pose_landmarker_lite.task   # Lightweight MediaPipe Pose model asset (~5.5MB)
├── requirements.txt            # Python dependencies (opencv-python, mediapipe, numpy)
└── README.md                   # Documentation & usage instructions
```

---

## How to Run

1. Run the application:
   ```powershell
   .\venv\Scripts\python.exe main.py
   ```

2. **Options**:
   - Select a specific camera index (e.g., if using an external USB camera on index 1):
     ```powershell
     .\venv\Scripts\python.exe main.py --camera 1
     ```
   - Change the evaluation interval (default is 5.0 seconds):
     ```powershell
     .\venv\Scripts\python.exe main.py --interval 5.0
     ```

---

## Keyboard Controls (In OpenCV Window)

| Key | Action |
|---|---|
| **`[C]`** | **Calibrate Baseline**: Captures your current upright posture as the baseline. |
| **`[R]`** | **Reset Defaults**: Restores default neck threshold (12.0°). |
| **`[M]`** | **Toggle Audio**: Mutes or unmutes warning sound effects. |
| **`[Q]`** or **`[ESC]`** | **Exit**: Safely releases the camera and closes all windows. |
