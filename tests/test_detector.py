"""detector.py のテスト"""

import os
import tempfile

import cv2
import numpy as np
import pytest

from microcam.config import DetectionConfig
from microcam.detector import Detector


@pytest.fixture
def detector():
    config = DetectionConfig(
        enabled=True, alpha=0.05, threshold=25, min_area=100, post_seconds=5
    )
    return Detector(config)


def make_frame(w=640, h=480, color=(128, 128, 128)):
    """均一色のテストフレームを生成"""
    frame = np.full((h, w, 3), color, dtype=np.uint8)
    return frame


def test_initial_frame_no_detection(detector):
    """最初のフレームでは検知されないこと"""
    frame = make_frame()
    detected, contours = detector.process_frame(frame)
    assert detected is False
    assert contours == []


def test_static_scene_no_detection(detector):
    """静止シーンでは検知されないこと"""
    frame = make_frame()
    # 背景モデル構築
    for _ in range(10):
        detector.process_frame(frame.copy())

    detected, contours = detector.process_frame(frame.copy())
    assert detected is False


def test_motion_detection(detector):
    """動きがあると検知されること"""
    bg = make_frame(color=(100, 100, 100))
    # 背景モデル構築
    for _ in range(20):
        detector.process_frame(bg.copy())

    # 大きな白い矩形を追加（動体）
    motion_frame = bg.copy()
    cv2.rectangle(motion_frame, (200, 150), (400, 350), (255, 255, 255), -1)

    detected, contours = detector.process_frame(motion_frame)
    assert detected is True
    assert len(contours) > 0


def test_small_motion_ignored(detector):
    """min_area未満の小さい動きは無視されること"""
    detector._config.min_area = 10000  # 非常に大きな閾値
    bg = make_frame(color=(100, 100, 100))
    for _ in range(20):
        detector.process_frame(bg.copy())

    motion_frame = bg.copy()
    # 小さな変化
    cv2.rectangle(motion_frame, (300, 240), (310, 250), (255, 255, 255), -1)

    detected, _ = detector.process_frame(motion_frame)
    assert detected is False


def test_mask_excludes_region(detector):
    """マスクで除外された領域では検知されないこと"""
    bg = make_frame(color=(100, 100, 100))
    for _ in range(20):
        detector.process_frame(bg.copy())

    # マスク作成（全体を黒=除外）
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        mask = np.zeros((480, 640), dtype=np.uint8)  # 全部除外
        cv2.imwrite(f.name, mask)
        detector.load_mask(f.name)

    # 動きがあっても検知されない
    motion_frame = bg.copy()
    cv2.rectangle(motion_frame, (200, 150), (400, 350), (255, 255, 255), -1)

    detected, _ = detector.process_frame(motion_frame)
    assert detected is False

    os.unlink(f.name)
