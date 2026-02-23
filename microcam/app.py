"""アプリケーション統合・オーケストレータ"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import TYPE_CHECKING

from flask import Flask

from .auth import require_auth
from .camera import Camera
from .config import AppConfig, load_config

if TYPE_CHECKING:
    from .detector import Detector
    from .notifier import Notifier
    from .recorder import Recorder
    from .storage import StorageManager

logger = logging.getLogger(__name__)


class MicroCamApp:
    """アプリケーション全体を管理するオーケストレータ"""

    def __init__(self, config: AppConfig | None = None):
        self.config = config or load_config()
        self.camera = Camera(self.config.camera)
        self.detector: Detector | None = None
        self.recorder: Recorder | None = None
        self.notifier: Notifier | None = None
        self.storage_manager: StorageManager | None = None
        self._detection_thread: threading.Thread | None = None
        self._running = False
        self._flask: Flask | None = None

    def _create_flask(self) -> Flask:
        template_dir = os.path.join(os.path.dirname(__file__), "web", "templates")
        static_dir = os.path.join(os.path.dirname(__file__), "web", "static")
        app = Flask(
            __name__,
            template_folder=template_dir,
            static_folder=static_dir,
        )

        # Basic認証を全ルートに適用
        auth = require_auth(self.config.web)

        from .web.api import api, init_api
        from .web.routes import init_routes, pages

        init_routes(self)
        init_api(self)

        # Blueprint登録前に認証デコレータを適用
        app.register_blueprint(pages)
        app.register_blueprint(api)

        @app.before_request
        def _auth():
            return auth(lambda: None)()

        # before_requestの認証を正しく適用するため修正
        app.before_request_funcs[None].clear()

        def _check_auth():
            from flask import request, Response
            from .auth import check_auth as _check
            auth_header = request.authorization
            if not auth_header or not _check(
                auth_header.username, auth_header.password, self.config.web
            ):
                return Response(
                    "認証が必要です",
                    401,
                    {"WWW-Authenticate": 'Basic realm="MicroCam"'},
                )

        app.before_request(_check_auth)

        return app

    def start(self) -> None:
        """全コンポーネントを起動"""
        self._running = True

        # データディレクトリ作成
        os.makedirs(self.config.recording.output_dir, exist_ok=True)
        os.makedirs(self.config.recording.snapshot_dir, exist_ok=True)

        # カメラ起動
        self.camera.start()

        # 動体検知エンジン
        from .detector import Detector

        self.detector = Detector(self.config.detection)
        mask_path = os.path.join(self.config.base_dir, "data", "mask.png")
        if os.path.exists(mask_path):
            self.detector.load_mask(mask_path)

        # レコーダー
        from .recorder import Recorder

        self.recorder = Recorder(self.config.recording, self.config.camera)

        # LINE通知
        from .notifier import Notifier

        self.notifier = Notifier(self.config.line)
        if self.config.line.enabled:
            self.notifier.start()

        # ストレージ管理
        from .storage import StorageManager

        self.storage_manager = StorageManager(
            self.config.storage, self.config.recording
        )
        self.storage_manager.start()

        # 検知ループスレッド
        self._detection_thread = threading.Thread(
            target=self._detection_loop, daemon=True
        )
        self._detection_thread.start()

        logger.info("MicroCam 全コンポーネント起動完了")

    def _detection_loop(self) -> None:
        """メイン検知+録画ループ"""
        interval = 1.0 / self.config.camera.fps
        last_detection_time = 0.0

        while self._running:
            frame = self.camera.frame
            if frame is None:
                time.sleep(0.1)
                continue

            t0 = time.monotonic()

            if self.config.detection.enabled and self.detector:
                detected, contours = self.detector.process_frame(frame)

                if detected:
                    last_detection_time = time.monotonic()

                    # 録画開始
                    if self.recorder and not self.recorder.is_recording:
                        # プリイベントバッファからフレームを供給
                        pre_frames = list(self.camera.buffer)
                        self.recorder.start_recording(pre_frames)
                        # スナップショット
                        self.recorder.capture_snapshot(frame)
                        # LINE通知
                        if self.notifier and self.config.line.enabled:
                            snap_path = self.recorder.last_snapshot_path
                            self.notifier.notify(snap_path)

                # 検知後の録画延長
                if self.recorder and self.recorder.is_recording:
                    self.recorder.feed_frame(frame)
                    elapsed = time.monotonic() - last_detection_time
                    if (
                        not detected
                        and elapsed > self.config.detection.post_seconds
                    ):
                        self.recorder.stop_recording()
            else:
                # 検知無効でも録画中なら停止
                if self.recorder and self.recorder.is_recording:
                    self.recorder.stop_recording()

            dt = time.monotonic() - t0
            sleep_time = interval - dt
            if sleep_time > 0:
                time.sleep(sleep_time)

    def stop(self) -> None:
        """全コンポーネントを停止"""
        self._running = False
        if self.recorder and self.recorder.is_recording:
            self.recorder.stop_recording()
        if self.notifier:
            self.notifier.stop()
        if self.storage_manager:
            self.storage_manager.stop()
        self.camera.stop()
        logger.info("MicroCam 全コンポーネント停止")

    def run(self) -> None:
        """Flask Webサーバーを起動（ブロッキング）"""
        self.start()
        self._flask = self._create_flask()
        try:
            self._flask.run(
                host=self.config.web.host,
                port=self.config.web.port,
                threaded=True,
                use_reloader=False,
            )
        finally:
            self.stop()
