import cv2
import os
import pyrealsense2 as rs
import numpy as np

def capture_images(save_dir):
    # Create the directory if it does not exist
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
    
    # Configure depth and color streams
    pipeline = rs.pipeline()
    config = rs.config()
    config.enable_stream(rs.stream.color, 1280, 720, rs.format.bgr8, 30)

    # Start streaming
    pipeline.start(config)
    
    print("Press 'c' to capture an image. Press 'q' to quit.")
    
    img_counter = 0
    
    try:
        while True:
            # Wait for a coherent pair of frames: depth and color
            frames = pipeline.wait_for_frames()
            color_frame = frames.get_color_frame()
            
            if not color_frame:
                continue
            
            # Convert images to numpy arrays
            color_image = np.asanyarray(color_frame.get_data())
            
            # Display the resulting frame
            cv2.imshow('Camera', color_image)
            
            # Wait for a key event
            key = cv2.waitKey(1) & 0xFF
            
            if key == ord('c'):
                # Capture the image
                img_name = os.path.join(save_dir, f"image_{img_counter}.png")
                cv2.imwrite(img_name, color_image)
                print(f"{img_name} captured!")
                img_counter += 1
            elif key == ord('q'):
                # Quit the loop
                break
    finally:
        # Stop streaming
        pipeline.stop()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    # Specify the directory to save images
    save_directory = "captured_images"
    capture_images(save_directory)

