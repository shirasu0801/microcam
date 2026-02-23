"""LINE通知"""

from __future__ import annotations

import logging
import queue
import threading
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import LineConfig

logger = logging.getLogger(__name__)


class Notifier:
    """LINE Messaging API経由のプッシュ通知"""

    def __init__(self, config: LineConfig):
        self._config = config
        self._queue: queue.Queue[str | None] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._running = False
        self._last_notify_time: float = 0

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()
        logger.info("LINE通知ワーカー開始")

    def stop(self) -> None:
        self._running = False
        self._queue.put(None)  # sentinel
        if self._thread:
            self._thread.join(timeout=5)

    def notify(self, snapshot_path: str | None = None) -> None:
        """通知をキューに追加（クールダウン制御）"""
        now = time.time()
        if now - self._last_notify_time < self._config.cooldown:
            return
        self._last_notify_time = now
        self._queue.put(snapshot_path or "")

    def send_test(self) -> None:
        """テスト通知を送信"""
        self._queue.put("__test__")

    def _worker(self) -> None:
        """通知送信ワーカースレッド"""
        while self._running:
            try:
                item = self._queue.get(timeout=1)
            except queue.Empty:
                continue

            if item is None:
                break

            try:
                self._send(item)
            except Exception:
                logger.exception("LINE通知送信エラー")

    def _send(self, snapshot_path: str) -> None:
        """実際にLINE APIを呼び出す"""
        import requests

        token = self._config.channel_access_token
        user_id = self._config.user_id
        if not token or not user_id:
            logger.warning("LINE設定が不完全です")
            return

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        is_test = snapshot_path == "__test__"
        text = "テスト通知です" if is_test else "動体を検知しました"

        messages = [{"type": "text", "text": text}]

        # スナップショットがある場合は画像メッセージを追加
        # 注意: LINE Messaging APIで画像を送信するにはURLが必要
        # ローカルファイルの場合はテキストのみ送信
        if snapshot_path and not is_test and snapshot_path != "":
            messages[0]["text"] += f"\n📷 スナップショット: {snapshot_path}"

        payload = {
            "to": user_id,
            "messages": messages,
        }

        resp = requests.post(
            "https://api.line.me/v2/bot/message/push",
            headers=headers,
            json=payload,
            timeout=10,
        )

        if resp.status_code == 200:
            logger.info("LINE通知送信成功")
        else:
            logger.error("LINE通知エラー: %s %s", resp.status_code, resp.text)
