import os
import cv2
from typing import TypedDict

class FrameInfo(TypedDict):
    frame: str
    blur_score: float
    is_blurry: bool
    is_duplicate: bool

def process_video(video_path: str, output_dir: str):
    """
    Reads a video, extracts every 5th frame, and yields frame information.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Could not open video file: {video_path}")
        
    frame_count = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
            
        if frame_count % 5 == 0:
            # Yield dummy info for now
            frame_filename = f"frames/{frame_count:04d}.jpg"
            yield FrameInfo(
                frame=frame_filename,
                blur_score=100.0,
                is_blurry=False,
                is_duplicate=False
            )
            
        frame_count += 1
        
    cap.release()
