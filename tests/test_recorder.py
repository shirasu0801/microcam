"""recorder.py のテスト"""

import os

import cv2
import numpy as np
import pytest

from microcam.config import CameraConfig, RecordingConfig
from microcam.recorder import Recorder


@pytest.fixture
def recorder(tmp_path):
    rec_config = RecordingConfig(
        pre_seconds=1,
        max_seconds=10,
        output_dir=str(tmp_path / "recordings"),
        snapshot_dir=str(tmp_path / "snapshots"),
    )
    cam_config = CameraConfig(device=0, width=640, height=480, fps=10)
    return Recorder(rec_config, cam_config)


def make_frame(w=640, h=480):
    return np.random.randint(0, 255, (h, w, 3), dtype=np.uint8)


def test_start_stop_recording(recorder, tmp_path):
    """録画の開始と停止が正常に動作すること"""
    assert recorder.is_recording is False

    path = recorder.start_recording()
    assert recorder.is_recording is True
    assert path != ""

    # フレーム書き込み
    for _ in range(5):
        recorder.feed_frame(make_frame())

    recorder.stop_recording()
    assert recorder.is_recording is False
    assert os.path.exists(path)


def test_pre_event_buffer(recorder, tmp_path):
    """プリイベントバッファのフレームが録画に含まれること"""
    pre_frames = [make_frame() for _ in range(10)]
    path = recorder.start_recording(pre_frames)

    for _ in range(5):
        recorder.feed_frame(make_frame())

    recorder.stop_recording()
    assert os.path.exists(path)

    # ファイルが空でないことを確認
    assert os.path.getsize(path) > 0


def test_capture_snapshot(recorder, tmp_path):
    """スナップショットが正しく保存されること"""
    frame = make_frame()
    path = recorder.capture_snapshot(frame)
    assert os.path.exists(path)
    assert path.endswith(".jpg")
    assert recorder.last_snapshot_path == path

    # 画像として読み込めることを確認
    img = cv2.imread(path)
    assert img is not None
    assert img.shape[0] == 480
    assert img.shape[1] == 640


def test_feed_without_recording(recorder):
    """録画中でなければfeed_frameは何もしないこと"""
    recorder.feed_frame(make_frame())  # エラーにならないこと


def test_stop_without_start(recorder):
    """録画してない状態でstop_recordingを呼んでもエラーにならないこと"""
    recorder.stop_recording()  # エラーにならないこと
