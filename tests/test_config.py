"""config.py のテスト"""

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from microcam.config import AppConfig, load_config, save_config


@pytest.fixture
def config_file(tmp_path):
    """テスト用設定ファイルを作成"""
    cfg = {
        "camera": {"device": 0, "width": 640, "height": 480, "fps": 10},
        "detection": {"enabled": True, "threshold": 30, "min_area": 200},
        "recording": {
            "pre_seconds": 2,
            "output_dir": "data/recordings",
            "snapshot_dir": "data/snapshots",
        },
        "storage": {"retention_days": 3, "max_gb": 10},
        "web": {"port": 9090, "username": "test", "password_hash": "$2b$12$test"},
        "line": {"enabled": False},
        "logging": {"level": "DEBUG"},
    }
    path = tmp_path / "config.yaml"
    with open(path, "w") as f:
        yaml.dump(cfg, f)
    return path


def test_load_config(config_file):
    """設定ファイルを正しく読み込めること"""
    cfg = load_config(config_file)
    assert cfg.camera.width == 640
    assert cfg.camera.height == 480
    assert cfg.camera.fps == 10
    assert cfg.detection.threshold == 30
    assert cfg.web.port == 9090
    assert cfg.web.username == "test"


def test_load_config_defaults():
    """設定ファイルがない場合デフォルト値が使われること"""
    cfg = load_config("/nonexistent/config.yaml")
    assert cfg.camera.width == 1280
    assert cfg.camera.height == 720
    assert cfg.camera.fps == 15
    assert cfg.detection.enabled is True
    assert cfg.web.port == 8080


def test_load_config_partial(tmp_path):
    """一部のみ指定した場合、残りはデフォルトになること"""
    cfg_data = {"camera": {"fps": 30}}
    path = tmp_path / "partial.yaml"
    with open(path, "w") as f:
        yaml.dump(cfg_data, f)

    cfg = load_config(path)
    assert cfg.camera.fps == 30
    assert cfg.camera.width == 1280  # デフォルト
    assert cfg.detection.enabled is True  # デフォルト


def test_save_config(tmp_path, config_file):
    """設定をYAMLに保存し再読み込みできること"""
    cfg = load_config(config_file)
    cfg.camera.fps = 25

    save_path = tmp_path / "saved.yaml"
    save_config(cfg, save_path)

    reloaded = load_config(save_path)
    assert reloaded.camera.fps == 25


def test_output_dirs_absolute(config_file):
    """出力ディレクトリが絶対パスに解決されること"""
    cfg = load_config(config_file)
    assert os.path.isabs(cfg.recording.output_dir)
    assert os.path.isabs(cfg.recording.snapshot_dir)
