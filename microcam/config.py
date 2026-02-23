"""設定ロード（YAML）"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class CameraConfig:
    device: int = 0
    width: int = 1280
    height: int = 720
    fps: int = 15


@dataclass
class DetectionConfig:
    enabled: bool = True
    alpha: float = 0.01
    threshold: int = 25
    min_area: int = 500
    post_seconds: int = 5


@dataclass
class RecordingConfig:
    pre_seconds: int = 3
    max_seconds: int = 300
    output_dir: str = "data/recordings"
    snapshot_dir: str = "data/snapshots"


@dataclass
class StorageConfig:
    retention_days: int = 7
    max_gb: float = 28
    cleanup_interval: int = 3600


@dataclass
class WebConfig:
    host: str = "0.0.0.0"
    port: int = 8080
    username: str = "admin"
    password_hash: str = ""


@dataclass
class LineConfig:
    enabled: bool = False
    channel_access_token: str = ""
    user_id: str = ""
    cooldown: int = 60


@dataclass
class LoggingConfig:
    level: str = "INFO"


@dataclass
class AppConfig:
    camera: CameraConfig = field(default_factory=CameraConfig)
    detection: DetectionConfig = field(default_factory=DetectionConfig)
    recording: RecordingConfig = field(default_factory=RecordingConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    web: WebConfig = field(default_factory=WebConfig)
    line: LineConfig = field(default_factory=LineConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    base_dir: str = ""


def _merge(dc_class, data: dict):
    """辞書からデータクラスを生成（未知キーは無視）"""
    if data is None:
        return dc_class()
    valid = {f.name for f in dc_class.__dataclass_fields__.values()}
    return dc_class(**{k: v for k, v in data.items() if k in valid})


def load_config(path: str | Path | None = None) -> AppConfig:
    """YAML設定ファイルを読み込みAppConfigを返す"""
    if path is None:
        path = os.environ.get("MICROCAM_CONFIG", "config/config.yaml")
    path = Path(path)

    if path.exists():
        with open(path, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    else:
        raw = {}

    base_dir = str(path.resolve().parent.parent)

    cfg = AppConfig(
        camera=_merge(CameraConfig, raw.get("camera")),
        detection=_merge(DetectionConfig, raw.get("detection")),
        recording=_merge(RecordingConfig, raw.get("recording")),
        storage=_merge(StorageConfig, raw.get("storage")),
        web=_merge(WebConfig, raw.get("web")),
        line=_merge(LineConfig, raw.get("line")),
        logging=_merge(LoggingConfig, raw.get("logging")),
        base_dir=base_dir,
    )

    # 出力ディレクトリを絶対パスに解決
    for attr in ("output_dir", "snapshot_dir"):
        val = getattr(cfg.recording, attr)
        if not os.path.isabs(val):
            setattr(cfg.recording, attr, os.path.join(base_dir, val))

    return cfg


def save_config(cfg: AppConfig, path: str | Path | None = None) -> None:
    """現在の設定をYAMLファイルに書き出す"""
    if path is None:
        path = os.environ.get("MICROCAM_CONFIG", "config/config.yaml")
    path = Path(path)

    from dataclasses import asdict
    data = asdict(cfg)
    # base_dirは書き出さない
    data.pop("base_dir", None)

    # output_dir/snapshot_dirを相対パスに戻す
    for attr in ("output_dir", "snapshot_dir"):
        val = data["recording"][attr]
        try:
            data["recording"][attr] = str(
                Path(val).relative_to(cfg.base_dir)
            )
        except ValueError:
            pass

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
