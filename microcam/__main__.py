"""MicroCam エントリーポイント"""

from __future__ import annotations

import argparse
import logging
import signal
import sys

from .config import load_config


def main() -> None:
    parser = argparse.ArgumentParser(description="MicroCam 監視カメラシステム")
    parser.add_argument(
        "-c", "--config", default=None, help="設定ファイルのパス (デフォルト: config/config.yaml)"
    )
    parser.add_argument(
        "--host", default=None, help="Webサーバーのホスト"
    )
    parser.add_argument(
        "--port", type=int, default=None, help="Webサーバーのポート"
    )
    parser.add_argument(
        "--debug", action="store_true", help="デバッグモード"
    )
    args = parser.parse_args()

    # 設定読み込み
    config = load_config(args.config)

    # ログ設定
    log_level = "DEBUG" if args.debug else config.logging.level
    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # コマンドラインオプションで上書き
    if args.host:
        config.web.host = args.host
    if args.port:
        config.web.port = args.port

    from .app import MicroCamApp

    app = MicroCamApp(config)

    # シグナルハンドラ（SIGTERM/SIGINT）
    def _shutdown(signum, frame):
        logging.getLogger(__name__).info("シャットダウンシグナル受信 (%s)", signum)
        app.stop()
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    logging.getLogger(__name__).info(
        "MicroCam 起動: http://%s:%d", config.web.host, config.web.port
    )
    app.run()


if __name__ == "__main__":
    main()
