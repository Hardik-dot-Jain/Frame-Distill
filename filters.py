import os
import cv2
from collections import deque
from pydantic import BaseModel
from calibrate_blur import calculate_blur
from classifier import CrimeClassifier

class FrameResult(BaseModel):
    frame: str
    blur_score: float
    is_blurry: bool
    is_duplicate: bool
    ssim_score: float
    event_label: str = "Normal"
    confidence: float = 0.0

def process_video(video_path: str, output_dir: str, blur_threshold: float = 100.0):
    """
    Reads a video, extracts every 5th frame, and yields frame information.
    Saves the frame if it is considered sharp.
    Buffers 16 frames to run action classification.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Could not open video file: {video_path}")
        
    classifier = CrimeClassifier()
    frame_buffer = deque(maxlen=16)
    
    current_event_label = "Normal"
    current_confidence = 0.0
        
    frame_count = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
            
        if frame_count % 5 == 0:
            blur_score = calculate_blur(frame)
            is_blurry = blur_score <= blur_threshold
            
            # Estimate uncompressed frame size in MB
            frame_size_mb = frame.nbytes / (1024 * 1024)
            
            frame_filename = f"frames/{frame_count:04d}.jpg"
            
            if not is_blurry:
                # Save the image if it is sharp
                save_path = os.path.join(output_dir, f"{frame_count:04d}.jpg")
                cv2.imwrite(save_path, frame)
                
                # Buffer the non-duplicate, sharp frame for classification
                frame_buffer.append(frame)
                
                # Run classification when buffer is full
                if len(frame_buffer) == 16:
                    current_event_label, current_confidence = classifier.detect_key_event(list(frame_buffer))
                    
                    # 4. Overlapping Temporal Windows (Stride Reduction)
                    # Pop the oldest 8 frames to create a 50% overlapping stride.
                    # The next inference will run after exactly 8 more sharp frames are buffered.
                    for _ in range(8):
                        frame_buffer.popleft()
                
            yield FrameResult(
                frame=frame_filename,
                blur_score=blur_score,
                is_blurry=is_blurry,
                is_duplicate=False,
                ssim_score=0.0,
                event_label=current_event_label,
                confidence=current_confidence
            ), frame_size_mb
            
        frame_count += 1
        
    cap.release()

if __name__ == "__main__":
    # Example usage
    test_video = "test_video.mp4"
    print(f"Starting video processing on {test_video}...")
    
    if not os.path.exists(test_video):
        print(f"Warning: {test_video} not found. Please provide a valid video path.")
    else:
        try:
            total_frames = 0
            good_frames = 0
            discarded_frames = 0
            saved_memory_mb = 0.0
            total_confidence = 0.0
            
            all_results = []
            
            for result, frame_size_mb in process_video(test_video, "frames", blur_threshold=100.0):
                print(result.model_dump())
                
                # If accuracy percentage (confidence) is more than 90%, print an alert
                if result.confidence > 0.90 and result.event_label != "Normal":
                    print(f"⚠️ [ALERT] High Accuracy Detection: '{result.event_label}' detected with {result.confidence*100:.2f}% accuracy at {result.frame}!")
                
                all_results.append(result.model_dump())
                
                total_frames += 1
                total_confidence += result.confidence
                
                if result.is_blurry or result.is_duplicate:
                    discarded_frames += 1
                    saved_memory_mb += frame_size_mb
                else:
                    good_frames += 1
                    
            avg_accuracy = (total_confidence / total_frames * 100) if total_frames > 0 else 0.0
                    
            print("\n" + "="*40)
            print("         PROCESSING SUMMARY")
            print("="*40)
            print(f"Total Frames Analyzed : {total_frames}")
            print(f"Good Frames Saved     : {good_frames}")
            print(f"Frames Discarded      : {discarded_frames}")
            print(f"Estimated Memory Saved: {saved_memory_mb:.2f} MB (uncompressed)")
            print(f"Average Model Accuracy: {avg_accuracy:.2f}%")
            print("="*40)
            
            # Export to Excel
            if all_results:
                import pandas as pd
                df = pd.DataFrame(all_results)
                excel_path = "frame_distill_results.xlsx"
                df.to_excel(excel_path, index=False)
                print(f"\n[SUCCESS] Information successfully exported to {excel_path} - ready to download!")
            
        except Exception as e:
            print(f"Error processing video: {e}")
