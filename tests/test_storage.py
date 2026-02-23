"""storage.py のテスト"""

import os
import time

import pytest

from microcam.config import RecordingConfig, StorageConfig
from microcam.storage import StorageManager


@pytest.fixture
def storage(tmp_path):
    rec_config = RecordingConfig(
        pre_seconds=1,
        max_seconds=10,
        output_dir=str(tmp_path / "recordings"),
        snapshot_dir=str(tmp_path / "snapshots"),
    )
    storage_config = StorageConfig(retention_days=7, max_gb=28, cleanup_interval=3600)
    os.makedirs(rec_config.output_dir)
    os.makedirs(rec_config.snapshot_dir)
    return StorageManager(storage_config, rec_config), rec_config


def create_file(dir_path, name, size=1024, age_days=0):
    """テスト用ファイルを作成"""
    path = os.path.join(dir_path, name)
    with open(path, "wb") as f:
        f.write(b"\x00" * size)
    if age_days > 0:
        mtime = time.time() - (age_days * 86400)
        os.utime(path, (mtime, mtime))
    return path


def test_get_usage(storage):
    sm, rec = storage
    create_file(rec.output_dir, "test1.mp4", size=2048)
    create_file(rec.output_dir, "test2.mp4", size=1024)
    create_file(rec.snapshot_dir, "snap1.jpg", size=512)

    usage = sm.get_usage()
    assert usage["total_bytes"] == 2048 + 1024 + 512
    assert usage["file_count"] == 3


def test_cleanup_old_files(storage):
    """保持日数を超えたファイルが削除されること"""
    sm, rec = storage
    sm._config.retention_days = 7

    # 古いファイル（8日前）
    old_path = create_file(rec.output_dir, "old.mp4", age_days=8)
    # 新しいファイル（1日前）
    new_path = create_file(rec.output_dir, "new.mp4", age_days=1)

    sm._cleanup()

    assert not os.path.exists(old_path)
    assert os.path.exists(new_path)


def test_cleanup_capacity_limit(storage):
    """容量上限を超えた場合古い順に削除されること"""
    sm, rec = storage
    sm._config.max_gb = 0.000003  # 約3KB

    # 3ファイル作成（各2KB = 合計6KB > 3KB上限）
    f1 = create_file(rec.output_dir, "oldest.mp4", size=2048, age_days=3)
    f2 = create_file(rec.output_dir, "middle.mp4", size=2048, age_days=2)
    f3 = create_file(rec.output_dir, "newest.mp4", size=2048, age_days=1)

    sm._cleanup()

    # 古い順に削除される
    assert not os.path.exists(f1)
    assert not os.path.exists(f2)
    assert os.path.exists(f3)


def test_empty_dirs(storage):
    """空ディレクトリでエラーにならないこと"""
    sm, _ = storage
    usage = sm.get_usage()
    assert usage["total_bytes"] == 0
    assert usage["file_count"] == 0
    sm._cleanup()  # エラーにならないこと
