"""REST APIエンドポイント"""

from __future__ import annotations

import os
from pathlib import Path

from flask import Blueprint, jsonify, request, send_file

api = Blueprint("api", __name__, url_prefix="/api")

_app_ref = None


def init_api(app_ref) -> None:
    global _app_ref
    _app_ref = app_ref


@api.route("/status")
def status():
    """システムステータス"""
    return jsonify(
        {
            "camera": _app_ref.camera.is_running,
            "fps": round(_app_ref.camera.actual_fps, 1),
            "detection": _app_ref.config.detection.enabled,
            "recording": (
                _app_ref.recorder.is_recording if _app_ref.recorder else False
            ),
        }
    )


@api.route("/detection", methods=["POST"])
def toggle_detection():
    """検知ON/OFFトグル"""
    data = request.get_json(force=True)
    enabled = data.get("enabled")
    if enabled is not None:
        _app_ref.config.detection.enabled = bool(enabled)
    return jsonify({"detection": _app_ref.config.detection.enabled})


@api.route("/recordings")
def list_recordings():
    """録画一覧"""
    rec_dir = Path(_app_ref.config.recording.output_dir)
    files = []
    if rec_dir.exists():
        for f in sorted(rec_dir.iterdir(), reverse=True):
            if f.suffix in (".mp4", ".avi"):
                stat = f.stat()
                files.append(
                    {
                        "name": f.name,
                        "size": stat.st_size,
                        "mtime": stat.st_mtime,
                    }
                )
    return jsonify(files)


@api.route("/recordings/<filename>")
def get_recording(filename: str):
    """録画ファイル配信"""
    rec_dir = Path(_app_ref.config.recording.output_dir)
    filepath = rec_dir / filename
    if not filepath.exists() or not filepath.is_relative_to(rec_dir):
        return jsonify({"error": "not found"}), 404
    return send_file(filepath, mimetype="video/mp4")


@api.route("/recordings/<filename>", methods=["DELETE"])
def delete_recording(filename: str):
    """録画ファイル削除"""
    rec_dir = Path(_app_ref.config.recording.output_dir)
    filepath = rec_dir / filename
    if not filepath.exists() or not filepath.is_relative_to(rec_dir):
        return jsonify({"error": "not found"}), 404
    filepath.unlink()
    return jsonify({"deleted": filename})


@api.route("/snapshots/<filename>")
def get_snapshot(filename: str):
    """スナップショット配信"""
    snap_dir = Path(_app_ref.config.recording.snapshot_dir)
    filepath = snap_dir / filename
    if not filepath.exists() or not filepath.is_relative_to(snap_dir):
        return jsonify({"error": "not found"}), 404
    return send_file(filepath, mimetype="image/jpeg")


@api.route("/mask", methods=["GET"])
def get_mask():
    """検知マスク取得"""
    mask_path = os.path.join(_app_ref.config.base_dir, "data", "mask.png")
    if not os.path.exists(mask_path):
        return jsonify({"error": "no mask"}), 404
    return send_file(mask_path, mimetype="image/png")


@api.route("/mask", methods=["PUT"])
def put_mask():
    """検知マスク保存"""
    import base64

    import cv2
    import numpy as np

    data = request.get_json(force=True)
    img_data = data.get("image", "")
    if "," in img_data:
        img_data = img_data.split(",", 1)[1]

    raw = base64.b64decode(img_data)
    arr = np.frombuffer(raw, dtype=np.uint8)
    mask = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)

    mask_path = os.path.join(_app_ref.config.base_dir, "data", "mask.png")
    os.makedirs(os.path.dirname(mask_path), exist_ok=True)
    cv2.imwrite(mask_path, mask)

    if _app_ref.detector:
        _app_ref.detector.load_mask(mask_path)

    return jsonify({"ok": True})


@api.route("/config", methods=["GET"])
def get_config():
    """現在の設定を返す"""
    from dataclasses import asdict

    cfg = asdict(_app_ref.config)
    cfg.pop("base_dir", None)
    # パスワードハッシュは返さない
    cfg["web"].pop("password_hash", None)
    return jsonify(cfg)


@api.route("/config", methods=["PUT"])
def put_config():
    """設定を更新"""
    data = request.get_json(force=True)
    cfg = _app_ref.config

    # detection設定
    if "detection" in data:
        for k, v in data["detection"].items():
            if hasattr(cfg.detection, k):
                setattr(cfg.detection, k, type(getattr(cfg.detection, k))(v))

    # recording設定
    if "recording" in data:
        for k, v in data["recording"].items():
            if hasattr(cfg.recording, k) and k not in ("output_dir", "snapshot_dir"):
                setattr(cfg.recording, k, type(getattr(cfg.recording, k))(v))

    # storage設定
    if "storage" in data:
        for k, v in data["storage"].items():
            if hasattr(cfg.storage, k):
                setattr(cfg.storage, k, type(getattr(cfg.storage, k))(v))

    # LINE設定
    if "line" in data:
        for k, v in data["line"].items():
            if hasattr(cfg.line, k):
                setattr(cfg.line, k, v)

    # パスワード変更
    if "web" in data and "password" in data["web"]:
        from ..auth import hash_password
        cfg.web.password_hash = hash_password(data["web"]["password"])

    from ..config import save_config
    save_config(cfg)

    return jsonify({"ok": True})


@api.route("/storage/usage")
def storage_usage():
    """ディスク使用量"""
    if _app_ref.storage_manager:
        return jsonify(_app_ref.storage_manager.get_usage())
    return jsonify({"total_bytes": 0, "file_count": 0})


@api.route("/line/test", methods=["POST"])
def test_line():
    """LINE通知テスト"""
    if _app_ref.notifier and _app_ref.config.line.enabled:
        _app_ref.notifier.send_test()
        return jsonify({"ok": True})
    return jsonify({"error": "LINE未設定"}), 400
