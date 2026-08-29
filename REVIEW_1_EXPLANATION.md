# Review 1
**Author:** Computer Vision Lead  
**Objective:** Proving the Data Contract and delivering a working, standalone Blur-Detection Engine.

---

## 1. 
The primary objective  has been successfully achieved. We have delivered a standalone, fully functioning **Blur-Detection Engine** capable of directly ingesting raw video feeds, analyzing frames in real-time, and filtering out low-quality imagery based on a mathematically sound threshold. 

Crucially, this milestone proves the viability of our **Locked Data Contract**—a standardized schema that guarantees all downstream roles (e.g., UI/UX, database engineering) receive clean, predictable, and strictly-typed data streams from the Computer Vision layer.

---

## 2. Locked Data Contract (Schema Breakdown)
To ensure absolute reliability across the pipeline, we enforce our data schema using Pydantic v2. Every processed frame yields a strictly validated `FrameResult` object.

| Field | Type | Purpose & Justification |
| :--- | :--- | :--- |
| `frame` | `str` | **Relative path** to the saved image (e.g., `frames/0000.jpg`). We use relative paths to ensure cross-platform compatibility and to prevent path-breaking issues when downstream roles access the dataset across different operating systems. |
| `blur_score` | `float` | Continuous value representing image sharpness. Kept as a raw float to allow the database to query/sort frames by maximum clarity. |
| `is_blurry` | `bool` | A derived boolean flag (`blur_score <= threshold`). Offloads conditional logic from the UI/database teams—they simply filter by this boolean. |
| `is_duplicate` | `bool` | Reserved flag for our upcoming SSIM pipeline. Currently defaults to `False`. |
| `ssim_score` | `float` | Reserved structural similarity metric for duplicate detection. Currently defaults to `0.0`. |
| `event_label` | `str` | Indicates the classified anomaly (e.g., "Abuse", "Burglary"). Defaults to `"Normal"`. |
| `confidence` | `float` | The probability score of the detected anomaly classification. |

---

## 3. Core Tech Stack & Role of Each Library

*   **OpenCV (`cv2`)**: The workhorse of our pipeline. Handles high-performance video decoding (`VideoCapture`), frame subsampling, image I/O (`imwrite`), and calculates the 2nd spatial derivative (Laplacian) required for edge extraction.
*   **NumPy (`np`)**: Facilitates the underlying C-optimized matrix math required to calculate the variance of our Laplacian matrices at scale.
*   **Pydantic v2**: Provides zero-overhead, strictly enforced validation for our data contract, immediately throwing errors if the pipeline attempts to output malformed data.
*   **PyTorch (`torch`, `torchvision`)**: Drives the anomaly classification inference pipeline using a 3D ResNet (`r3d_18`) on a buffered queue of high-quality frames.

---

## 4. Mathematical & Algorithmic Logic

### Variance of Laplacian Method
To detect blur, we must identify the presence (or absence) of edges in an image. Sharp images possess crisp edges, which represent rapid changes in pixel intensity. 

1.  **Grayscale Conversion**: We first collapse the (B, G, R) color channels into a single intensity channel to eliminate noise.
2.  **Laplacian Operator**: We convolve the grayscale image with the Laplacian kernel. The Laplacian calculates the **2nd spatial derivative** ($\nabla^2 f$) of the image:
    $$ \nabla^2 f = \frac{\partial^2 f}{\partial x^2} + \frac{\partial^2 f}{\partial y^2} $$
    This operation highlights regions of rapid intensity change (edges).
3.  **Variance Calculation**: We calculate the variance ($\sigma^2$) of the resulting Laplacian matrix. 
    *   **High Variance** = High spread of edge responses = **Sharp Image**.
    *   **Low Variance** = Very few edge responses = **Blurry Image**.

### Subsampling & Memory Management
Processing 30+ frames per second (FPS) is computationally expensive and yields largely redundant data. 
*   **Subsampling**: We evaluate only every 5th frame (`frame_count % 5 == 0`), reducing processing overhead by 80% while retaining temporal context.
*   **Generators**: Instead of loading all frames into RAM, `process_video` is structured as a Python generator (`yield`). This ensures memory remains perfectly flat ($O(1)$) regardless of whether the video is 10 seconds or 10 hours long.

---

## 5. Calibration Findings (Kaggle Dataset)
To determine the mathematical boundary between "sharp" and "blurry", we engineered a standalone calibration script (`calibrate_blur.py`).

We executed this script against a curated sample of the **Kaggle Blur Dataset**, parsing images from three distinct categories: `defocused_blurred`, `motion_blurred`, and `sharp`. 

**Empirical Results:**
By analyzing the maximum variance of the blurred datasets and the minimum variance of the sharp dataset, we identified a clear separation. We automatically calculated the optimal empirical threshold to be **`100.0`**. Any variance score falling below this threshold is flagged by the pipeline as `is_blurry = True`.

---

## 6. Live Demo Walkthrough for Evaluators

To test the 30% pipeline on your own machine, follow these steps:

1.  Ensure you have a test video named `test_video.mp4` placed in the root of the project directory.
2.  Open your terminal and execute the pipeline:
    ```bash
    python filters.py
    ```

**Expected Console Output:**
You will immediately see a stream of JSON-like dictionaries printed to the console as the generator yields them in real-time, followed by a final processing summary:
```json
{'frame': 'frames/0000.jpg', 'blur_score': 185.43, 'is_blurry': False, 'is_duplicate': False, 'ssim_score': 0.0, 'event_label': 'Assault', 'confidence': 0.46}
...
========================================
         PROCESSING SUMMARY
========================================
Total Frames Analyzed : 684
Good Frames Saved     : 575
Frames Discarded      : 109
Estimated Memory Saved: 23.95 MB (uncompressed)
========================================
```

**Expected File System State:**
The pipeline will automatically generate a `frames/` directory. If you inspect this folder, you will find that it is populated strictly with high-quality, perfectly sharp `.jpg` images—all blurry and distorted frames will have been successfully ignored. Additionally, an Excel file (`frame_distill_results.xlsx`) containing the structured data for every frame will be saved to the root directory.
