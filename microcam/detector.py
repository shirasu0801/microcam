"""動体検知エンジン"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import cv2
import numpy as np

if TYPE_CHECKING:
    from .config import DetectionConfig

logger = logging.getLogger(__name__)


class Detector:
    """背景差分ベースの動体検知"""

    def __init__(self, config: DetectionConfig):
        self._config = config
        self._bg: np.ndarray | None = None
        self._mask: np.ndarray | None = None
        self._frame_count = 0

    def load_mask(self, path: str) -> None:
        """検知除外マスクを読み込む（白=検知対象、黒=除外）"""
        mask = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        if mask is not None:
            self._mask = mask
            logger.info("検知マスクを読み込みました: %s", path)

    def process_frame(
        self, frame: np.ndarray
    ) -> tuple[bool, list[np.ndarray]]:
        """
        フレームを処理し、動体検知結果を返す。

        Returns:
            (detected, contours): 検知有無と輪郭リスト
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)

        # 背景モデル初期化
        if self._bg is None:
            self._bg = gray.astype(np.float64)
            self._frame_count += 1
            return False, []

        # 背景更新（accumulateWeighted）
        cv2.accumulateWeighted(gray, self._bg, self._config.alpha)
        self._frame_count += 1

        # 差分計算
        delta = cv2.absdiff(gray, cv2.convertScaleAbs(self._bg))

        # 二値化
        _, thresh = cv2.threshold(
            delta, self._config.threshold, 255, cv2.THRESH_BINARY
        )

        # マスク適用（黒=除外領域をゼロに）
        if self._mask is not None:
            resized_mask = cv2.resize(
                self._mask, (thresh.shape[1], thresh.shape[0])
            )
            thresh = cv2.bitwise_and(thresh, resized_mask)

        # 膨張処理でノイズ除去
        thresh = cv2.dilate(thresh, None, iterations=2)

        # 輪郭検出
        contours, _ = cv2.findContours(
            thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        # 面積フィルタ
        significant = [
            c for c in contours if cv2.contourArea(c) >= self._config.min_area
        ]

        detected = len(significant) > 0

        # バウンディングボックスをフレームに描画
        if detected:
            for c in significant:
                x, y, w, h = cv2.boundingRect(c)
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
            cv2.putText(
                frame,
                "MOTION DETECTED",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 0, 255),
                2,
            )

        return detected, significant
