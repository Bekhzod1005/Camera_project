import cv2
import sys

def start_camera_feed(camera_index=0):
    # Initialize the USB camera capture
    # Note: On Windows, passing cv2.CAP_DSHOW can speed up camera initialization:
    # cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
    cap = cv2.VideoCapture(camera_index)

    if not cap.isOpened():
        print(f"Error: Could not open USB camera at index {camera_index}.")
        sys.exit(1)

    # Optional: Request specific resolution (e.g., 1280x720)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    print("Camera feed started successfully. Press 'q' in the video window to exit.")

    while True:
        # Read a frame from the camera
        ret, frame = cap.read()

        if not ret:
            print("Error: Failed to grab frame from the camera.")
            break

        # Display the live frame in a window
        cv2.imshow("USB Camera Feed", frame)

        # Wait 1ms for key press; exit loop if 'q' is pressed
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    # Clean up hardware resources and close windows
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    # Change to 1 or 2 if 0 opens your built-in webcam instead of the USB camera
    CAMERA_INDEX = 0
    start_camera_feed(CAMERA_INDEX)