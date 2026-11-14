# AI Side-View Posture Guardian (+ "FUCK YOU ISSA" Discord Easter Egg)

A real-time posture analysis system powered by OpenCV and MediaPipe Pose that monitors your posture from a side-view camera, evaluates alignment every 5 seconds, and triggers an intelligent desktop pop-up alert warning you to straighten your **Neck**, **Back**, or **Both**. OpenCV continuously checks whether your posture has returned to a healthy state and dismisses the alert once corrected.

---

## What's New

### 1. Precision Posture Thresholds (Neck: 12.0°, Back: 20.0°)
- Strict cervical alignment: Forward head tilt exceeding **12.0 degrees** from the plumb line immediately triggers the neck warning.
- Back / Torso alignment: Trunk slouching exceeding **20.0 degrees** triggers the back warning.
- Calibration is capped at **12.0° max** for neck.

### 2. Discord Microphone Audio Broadcast
- When you flip off the camera with a middle finger, the application broadcasts **"fuck you issa"** into your audio output AND any Virtual Microphone Cable detected (e.g., VB-Cable / Voicemeeter) so people in your **Discord call** hear it spoken directly through your mic!
- **How to route directly into your Discord Mic**:
  1. Download and install free [VB-Audio Virtual Cable](https://vb-audio.com/Cable/).
  2. In Discord: **User Settings $\rightarrow$ Voice & Video $\rightarrow$ Input Device $\rightarrow$ Select "CABLE Output"**.
  3. The application automatically detects `CABLE Input` and routes the voice straight into your Discord call.

---

## Posture Reference: Middle of Shoulder to Middle of Ear

The cervical alignment axis is computed from the **middle of the shoulders** to the **middle of the ears**:
- **Middle of the Ears (`Mid-Ear`)**: The exact anatomical midpoint between the left ear tragus and right ear tragus (the head/skull pivot axis).
- **Middle of the Shoulders (`Mid-Shoulder`)**: The exact anatomical midpoint between the left acromion and right acromion (the base of the neck / C7 cervicothoracic junction).
- **Middle of the Hips (`Mid-Hip`)**: The midpoint between left and right hips (base of the spine / pelvis center).

---

## Features

- **Progressive Volume Posture Alerts**:
  - The longer your poor posture persists across consecutive 5-second intervals, the louder and more urgent the alarm gets!
    - **Level 1 (5s)**: Gentle single chime at **25% volume** (650 Hz).
    - **Level 2 (10s)**: Double alert chime at **50% volume** (780 Hz).
    - **Level 3 (15s)**: Urgent triple chime at **75% volume** (950 Hz).
    - **Level 4+ (20s+)**: Maximum intensity 4-beep alarm at **100% volume** (1200 Hz).
  - The moment OpenCV verifies that your posture is straightened, the volume immediately resets to Level 1 and a pleasant success arpeggio plays.
- **"FUCK YOU ISSA" Fullscreen & Discord Mic Easter Egg**:
  - Automatically triggers a bold, red fullscreen pop-up across your entire display.
  - Broadcasts "fuck you issa" through your mic input for Discord.
  - Auto-dismisses when you lower your hand or press `[ESC]` / click anywhere.
- **5-Second Assessment Cycle & Verification**:
  - Automatically evaluates your posture every 5 seconds.
  - Progress bar in the HUD shows real-time countdown to the next evaluation.
  - OpenCV enters active verification mode after an alert to detect when you straighten up.
- **One-Key Upright Calibration**:
  - Press `[C]` while sitting upright in your ideal posture to set a personalized baseline (capped at 12° for neck).
  - Press `[R]` to reset back to default clinical thresholds (Neck: 12°, Back: 20°).

---

## Project Structure

```
opencv-usb-camera/
├── main.py                     # Main application entry point & OpenCV video loop
├── posture_analyzer.py         # Mid-shoulder to mid-ear posture reference & angles (15° threshold)
├── gesture_detector.py         # 21-point hand landmark middle finger gesture recognizer
├── posture_popup.py            # Tkinter posture alert & fullscreen "FUCK YOU ISSA" overlay
├── sound_effects.py            # Progressive volume synthesis & Discord mic broadcast router
├── fuck_you_issa.wav           # Voice audio clip ("fuck you issa")
├── pose_landmarker_full.task   # MediaPipe Pose Landmarker model asset
├── hand_landmarker.task        # MediaPipe Hand Landmarker model asset
├── requirements.txt            # Python dependencies
└── README.md                   # Documentation & usage instructions
```

---

## How to Run

1. Run the application:
   ```powershell
   .\venv\Scripts\python.exe main.py
   ```

2. **Options**:
   - Select a specific camera index (e.g. index 1 for USB camera):
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
| **`[R]`** | **Reset Defaults**: Restores default thresholds (Neck: 12°, Back: 20°). |
| **`[M]`** | **Toggle Audio**: Mutes or unmutes warning sound effects. |
| **`[Q]`** or **`[ESC]`** | **Exit**: Safely releases the camera and closes all windows. |
