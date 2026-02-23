"""録画・スナップショット"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime
from typing import TYPE_CHECKING

import cv2
import numpy as np

if TYPE_CHECKING:
    from .config import CameraConfig, RecordingConfig

logger = logging.getLogger(__name__)


class Recorder:
    """動体検知時の録画とスナップショット"""

    def __init__(self, config: RecordingConfig, camera_config: CameraConfig):
        self._config = config
        self._cam_config = camera_config
        self._writer: cv2.VideoWriter | None = None
        self._is_recording = False
        self._recording_start: float = 0
        self._current_path: str = ""
        self._frame_count = 0
        self.last_snapshot_path: str = ""

    @property
    def is_recording(self) -> bool:
        return self._is_recording

    def start_recording(self, pre_frames: list[np.ndarray] | None = None) -> str:
        """録画を開始する"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"rec_{timestamp}.mp4"
        self._current_path = os.path.join(self._config.output_dir, filename)

        os.makedirs(self._config.output_dir, exist_ok=True)

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        self._writer = cv2.VideoWriter(
            self._current_path,
            fourcc,
            self._cam_config.fps,
            (self._cam_config.width, self._cam_config.height),
        )

        if not self._writer.isOpened():
            logger.error("VideoWriter を開けません: %s", self._current_path)
            self._writer = None
            return ""

        self._is_recording = True
        self._recording_start = time.monotonic()
        self._frame_count = 0

        # プリイベントバッファを書き込み
        if pre_frames:
            for frame in pre_frames:
                if frame.shape[1] != self._cam_config.width or frame.shape[0] != self._cam_config.height:
                    frame = cv2.resize(frame, (self._cam_config.width, self._cam_config.height))
                self._writer.write(frame)
                self._frame_count += 1

        logger.info("録画開始: %s", self._current_path)
        return self._current_path

    def feed_frame(self, frame: np.ndarray) -> None:
        """録画中のフレームを書き込む"""
        if not self._is_recording or self._writer is None:
            return

        # 最大録画時間チェック
        elapsed = time.monotonic() - self._recording_start
        if elapsed > self._config.max_seconds:
            self.stop_recording()
            return

        if frame.shape[1] != self._cam_config.width or frame.shape[0] != self._cam_config.height:
            frame = cv2.resize(frame, (self._cam_config.width, self._cam_config.height))

        self._writer.write(frame)
        self._frame_count += 1

    def stop_recording(self) -> None:
        """録画を停止する"""
        if not self._is_recording:
            return
        self._is_recording = False
        if self._writer:
            self._writer.release()
            self._writer = None
        logger.info(
            "録画停止: %s (%d frames)", self._current_path, self._frame_count
        )

    def capture_snapshot(self, frame: np.ndarray) -> str:
        """スナップショットを保存する"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"snap_{timestamp}.jpg"
        path = os.path.join(self._config.snapshot_dir, filename)

        os.makedirs(self._config.snapshot_dir, exist_ok=True)
        cv2.imwrite(path, frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        self.last_snapshot_path = path
        logger.info("スナップショット: %s", path)
        return path
