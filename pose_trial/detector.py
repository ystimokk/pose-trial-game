"""MediaPipe Pose Landmarker wrapper for multi-person detection."""

import os
import ssl
import urllib.request

import certifi
import cv2
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision

from .config import AppConfig


def ensure_model(cfg: AppConfig) -> str:
    """Download the pose landmarker model if it isn't present yet."""
    path = cfg.model_path
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        print(f"Downloading pose model to {path} ...")
        context = ssl.create_default_context(cafile=certifi.where())
        with urllib.request.urlopen(cfg.model_url, context=context) as resp, open(path, "wb") as f:
            f.write(resp.read())
        print("Model downloaded.")
    return path


class PoseDetector:
    """Detects up to `num_poses` people per frame in VIDEO mode."""

    def __init__(self, cfg: AppConfig, num_poses: int):
        model_path = ensure_model(cfg)
        options = mp_vision.PoseLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=model_path),
            running_mode=mp_vision.RunningMode.VIDEO,
            num_poses=num_poses,
            min_pose_detection_confidence=cfg.min_pose_detection_confidence,
            min_pose_presence_confidence=cfg.min_pose_presence_confidence,
            min_tracking_confidence=cfg.min_tracking_confidence,
        )
        self._landmarker = mp_vision.PoseLandmarker.create_from_options(options)

    def detect(self, frame_bgr, timestamp_ms: int):
        """Returns a list of landmark lists, one per detected person."""
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = self._landmarker.detect_for_video(mp_image, timestamp_ms)
        return result.pose_landmarks or []

    def close(self):
        self._landmarker.close()
