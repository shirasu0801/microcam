"""ストレージ管理・自動削除"""

from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import RecordingConfig, StorageConfig

logger = logging.getLogger(__name__)


class StorageManager:
    """録画・スナップショットの自動クリーンアップ"""

    def __init__(self, config: StorageConfig, recording_config: RecordingConfig):
        self._config = config
        self._rec_config = recording_config
        self._thread: threading.Thread | None = None
        self._running = False

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._thread.start()
        logger.info("ストレージクリーンアップスレッド開始")

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def get_usage(self) -> dict:
        """ディスク使用量を取得"""
        total = 0
        count = 0
        for dir_path in (self._rec_config.output_dir, self._rec_config.snapshot_dir):
            p = Path(dir_path)
            if p.exists():
                for f in p.iterdir():
                    if f.is_file():
                        total += f.stat().st_size
                        count += 1
        return {"total_bytes": total, "file_count": count}

    def _cleanup_loop(self) -> None:
        """定期クリーンアップループ"""
        # 起動時に一度実行
        self._cleanup()

        while self._running:
            # インターバルを小刻みにスリープして停止に即応答
            for _ in range(self._config.cleanup_interval):
                if not self._running:
                    return
                time.sleep(1)
            self._cleanup()

    def _cleanup(self) -> None:
        """古いファイルの削除と容量制限"""
        now = time.time()
        max_age = self._config.retention_days * 86400
        max_bytes = self._config.max_gb * 1024 * 1024 * 1024
        deleted = 0

        all_files: list[tuple[Path, float, int]] = []

        for dir_path in (self._rec_config.output_dir, self._rec_config.snapshot_dir):
            p = Path(dir_path)
            if not p.exists():
                continue
            for f in p.iterdir():
                if not f.is_file():
                    continue
                stat = f.stat()
                age = now - stat.st_mtime

                # 保持日数超過
                if age > max_age:
                    f.unlink()
                    deleted += 1
                    logger.info("期限超過ファイル削除: %s", f.name)
                else:
                    all_files.append((f, stat.st_mtime, stat.st_size))

        # 容量制限チェック（古い順に削除）
        all_files.sort(key=lambda x: x[1])
        total = sum(s for _, _, s in all_files)

        while total > max_bytes and all_files:
            f, _, size = all_files.pop(0)
            f.unlink()
            total -= size
            deleted += 1
            logger.info("容量超過ファイル削除: %s", f.name)

        if deleted:
            logger.info("クリーンアップ完了: %d ファイル削除", deleted)
