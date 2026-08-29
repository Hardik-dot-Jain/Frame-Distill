import torch
import torchvision.models.video as video_models
import numpy as np
import cv2
import torch.nn.functional as F

class CrimeClassifier:
    def __init__(self):
        # Load lightweight pre-trained video model
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        try:
            self.model = video_models.r3d_18(weights=video_models.R3D_18_Weights.DEFAULT)
        except AttributeError:
            # Fallback for older torchvision versions
            self.model = video_models.r3d_18(pretrained=True)
            
        self.model.eval()
        self.model.to(self.device)
        
        # Dummy dictionary mapping of UCF-Crime labels
        # (Top indices mapped to crime types for demonstration)
        self.labels = {
            0: "Normal",
            1: "Abuse",
            2: "Arrest",
            3: "Arson",
            4: "Assault",
            5: "Burglary",
            6: "Explosion",
            7: "Fighting",
            8: "RoadAccidents",
            9: "Robbery",
            10: "Shooting",
            11: "Shoplifting",
            12: "Stealing",
            13: "Vandalism"
        }
        
    def detect_key_event(self, frame_buffer: list) -> tuple[str, float]:
        """
        Accepts a list of OpenCV frames, converts them to a 4D PyTorch tensor (C, T, H, W),
        runs inference, and returns a tuple: (event_label: str, confidence: float).
        """
        if len(frame_buffer) < 16:
            return "Normal", 0.0
            
        # Convert list of frames to numpy array: (T, H, W, C)
        frames_np = np.stack(frame_buffer)
        
        # Convert BGR to RGB
        frames_np = frames_np[..., ::-1]
        
        # Convert to tensor and permute to (C, T, H, W)
        tensor = torch.from_numpy(frames_np.copy()).float()
        tensor = tensor.permute(3, 0, 1, 2)
        
        # Normalize to [0, 1]
        tensor = tensor / 255.0
        
        # r3d_18 expects inputs of shape (N, C, D, H, W) with spatial size 112x112
        # We add the batch dimension and interpolate
        tensor = tensor.unsqueeze(0)
        tensor = F.interpolate(tensor, size=(16, 112, 112), mode='trilinear', align_corners=False)
        
        tensor = tensor.to(self.device)
        
        with torch.no_grad():
            outputs = self.model(tensor)
            probabilities = F.softmax(outputs, dim=1)
            confidence, predicted = torch.max(probabilities, 1)
            
            # Map prediction index to dummy UCF-Crime labels
            pred_idx = predicted.item() % len(self.labels)
            conf = confidence.item()
            
        label = self.labels.get(pred_idx, "Normal")
        return label, conf
