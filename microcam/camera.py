"""カメラキャプチャスレッド"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from typing import TYPE_CHECKING

import cv2
import numpy as np

if TYPE_CHECKING:
    from .config import CameraConfig

logger = logging.getLogger(__name__)


class Camera:
    """USB Webカメラからフレームをキャプチャするスレッド"""

    def __init__(self, config: CameraConfig):
        self._config = config
        self._cap: cv2.VideoCapture | None = None
        self._frame: np.ndarray | None = None
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None
        # プリイベント用リングバッファ（detector/recorderから参照）
        self._buffer: deque[np.ndarray] = deque(maxlen=config.fps * 5)
        self._frame_count = 0
        self._actual_fps = 0.0

    @property
    def frame(self) -> np.ndarray | None:
        with self._lock:
            return self._frame.copy() if self._frame is not None else None

    @property
    def buffer(self) -> deque[np.ndarray]:
        return self._buffer

    @property
    def actual_fps(self) -> float:
        return self._actual_fps

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        logger.info("カメラスレッド開始 (device=%s)", self._config.device)

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        if self._cap:
            self._cap.release()
            self._cap = None
        logger.info("カメラスレッド停止")

    def _open(self) -> bool:
        """カメラデバイスを開く（再接続対応）"""
        if self._cap and self._cap.isOpened():
            return True
        try:
            self._cap = cv2.VideoCapture(self._config.device)
            if not self._cap.isOpened():
                logger.error("カメラを開けません: device=%s", self._config.device)
                return False
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._config.width)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._config.height)
            self._cap.set(cv2.CAP_PROP_FPS, self._config.fps)
            logger.info(
                "カメラ接続: %dx%d @ %dfps",
                int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                int(self._cap.get(cv2.CAP_PROP_FPS)),
            )
            return True
        except Exception:
            logger.exception("カメラ初期化エラー")
            return False

    def _capture_loop(self) -> None:
        interval = 1.0 / self._config.fps
        fps_counter = 0
        fps_time = time.monotonic()

        while self._running:
            if not self._open():
                time.sleep(2)
                continue

            t0 = time.monotonic()
            ret, frame = self._cap.read()
            if not ret:
                logger.warning("フレーム取得失敗、カメラ再接続を試みます")
                self._cap.release()
                self._cap = None
                time.sleep(1)
                continue

            with self._lock:
                self._frame = frame
            self._buffer.append(frame)
            self._frame_count += 1

            # FPS計測
            fps_counter += 1
            elapsed = time.monotonic() - fps_time
            if elapsed >= 1.0:
                self._actual_fps = fps_counter / elapsed
                fps_counter = 0
                fps_time = time.monotonic()

            # フレームレート制御
            dt = time.monotonic() - t0
            sleep_time = interval - dt
            if sleep_time > 0:
                time.sleep(sleep_time)
