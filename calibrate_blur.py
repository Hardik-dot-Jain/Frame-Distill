import os
import cv2
import numpy as np
import glob

def calculate_blur(image) -> float:
    """Calculate the blur score of an image using Variance of Laplacian."""
    if isinstance(image, str):
        img = cv2.imread(image)
    else:
        img = image
    if img is None:
        return 0.0
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return cv2.Laplacian(gray, cv2.CV_64F).var()

def calibrate_threshold(dataset_path: str, sample_size: int = 100):
    """
    Calibrate blur threshold using a dataset containing 
    'defocused_blurred', 'motion_blurred', and 'sharp' folders.
    """
    categories = {
        'sharp': [],
        'defocused_blurred': [],
        'motion_blurred': []
    }
    
    for category in categories.keys():
        category_dir = os.path.join(dataset_path, category)
        if not os.path.exists(category_dir):
            print(f"Warning: Directory not found - {category_dir}")
            continue
            
        # Sample a subset of images
        image_paths = []
        for ext in ('*.jpg', '*.jpeg', '*.png', '*.JPG'):
            image_paths.extend(glob.glob(os.path.join(category_dir, ext)))
            
        image_paths = image_paths[:sample_size]
        
        for path in image_paths:
            score = calculate_blur(path)
            categories[category].append(score)
            
    # Calculate stats
    stats = {}
    for category, scores in categories.items():
        if not scores:
            stats[category] = {'avg': 0, 'min': 0, 'max': 0}
            continue
        stats[category] = {
            'avg': np.mean(scores),
            'min': np.min(scores),
            'max': np.max(scores)
        }
        
    print("--- Calibration Results ---")
    for category, stat in stats.items():
        print(f"[{category}] Avg: {stat['avg']:.2f}, Min: {stat['min']:.2f}, Max: {stat['max']:.2f}")
        
    sharp_min = stats['sharp']['min'] if stats['sharp']['min'] > 0 else 0
    blur_defocused_max = stats['defocused_blurred']['max'] if stats['defocused_blurred']['max'] > 0 else 0
    blur_motion_max = stats['motion_blurred']['max'] if stats['motion_blurred']['max'] > 0 else 0
    
    max_blur = max(blur_defocused_max, blur_motion_max)
    
    if max_blur < sharp_min:
        suggested_threshold = (max_blur + sharp_min) / 2.0
    else:
        # Fallback if overlap exists
        suggested_threshold = max_blur
        
    print(f"\nSuggested Optimal Blur Threshold: {suggested_threshold:.2f}")
    return suggested_threshold

if __name__ == "__main__":
    # Example usage (update with actual dataset path)
    dataset_path = "path/to/kaggle_blur_dataset"
    print(f"Starting calibration in {dataset_path}...")
    # threshold = calibrate_threshold(dataset_path)
