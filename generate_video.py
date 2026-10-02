import cv2
import numpy as np

def main():
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter('video.mp4', fourcc, 30.0, (640, 480))

    for i in range(300):
        # Create a blank black frame
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # Draw a moving white rectangle (simulates a moving object)
        x = int(50 + i * 2) % 500
        y = int(100 + i * 1) % 300
        cv2.rectangle(frame, (x, y), (x + 100, y + 80), (255, 255, 255), -1)
        
        # Draw text showing the frame number
        cv2.putText(frame, f"Forge Simulation Frame {i}", (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
        
        out.write(frame)

    out.release()
    print("Generated video.mp4 successfully.")

if __name__ == '__main__':
    main()
