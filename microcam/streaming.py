"""MJPEGストリーム生成"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Generator

import cv2

if TYPE_CHECKING:
    from .camera import Camera


def generate_mjpeg(camera: Camera, fps: int = 15) -> Generator[bytes, None, None]:
    """MJPEGストリーム用のフレームジェネレータ"""
    interval = 1.0 / fps
    while True:
        frame = camera.frame
        if frame is None:
            time.sleep(0.1)
            continue

        ret, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        if not ret:
            continue

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + jpeg.tobytes() + b"\r\n"
        )
        time.sleep(interval)
