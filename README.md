# MicroCam

Raspberry Pi + USB Webカメラで構築する **低コスト監視カメラシステム** です。
動体検知・自動録画・LINE通知・Web UIを備え、32GB SDカード1枚で24時間365日の監視運用を実現します。

---

## 目次

- [プロジェクト概要](#プロジェクト概要)
- [主な機能](#主な機能)
- [要件](#要件)
- [事前準備](#事前準備)
- [インストール](#インストール)
- [設定](#設定)
- [起動・実行](#起動実行)
- [Web UI の使い方](#web-ui-の使い方)
- [コマンドラインオプション](#コマンドラインオプション)
- [REST API リファレンス](#rest-api-リファレンス)
- [スレッドアーキテクチャ](#スレッドアーキテクチャ)
- [フォルダ構成と各ファイルの説明](#フォルダ構成と各ファイルの説明)
- [テスト](#テスト)
- [トラブルシューティング](#トラブルシューティング)
- [次回に向けた改善ポイント](#次回に向けた改善ポイント)
- [運用面のネクストアクション](#運用面のネクストアクション)

---

## プロジェクト概要

自宅・オフィス・ガレージなどの簡易セキュリティ用途を想定した監視カメラシステムです。
Raspberry Pi に USB Webカメラを接続するだけで、以下の一連のワークフローが自動化されます。

```
カメラ映像 → 動体検知 → 自動録画 + スナップショット → LINE通知 → 古いファイル自動削除
              ↓
        ブラウザでライブ視聴・録画再生・設定変更
```

### 技術スタック

| 領域 | 技術 | 選定理由 |
|------|------|----------|
| 映像処理 | Python + OpenCV (`opencv-python-headless`) | GIL解放あり、pip一発で導入可 |
| Web | Flask + Basic認証 + MJPEG配信 | 軽量・LAN内少人数向けに最適 |
| 通知 | LINE Messaging API (`line-bot-sdk`) | 日本で普及率が高く設定が容易 |
| 設定 | YAML (`PyYAML`) | 人間が読み書きしやすい |
| 認証 | bcrypt | パスワードハッシュの業界標準 |
| 背景モデル | `accumulateWeighted` | 照明変化に強く、計算コストが低い |
| コーデック | mp4v | pip版OpenCVでH.264非対応のため互換性優先 |

---

## 主な機能

| 機能 | 説明 |
|------|------|
| ライブ配信 | 720p / 15fps のMJPEGストリームをブラウザに配信 |
| 動体検知 | 背景差分（accumulateWeighted）+ 輪郭面積フィルタ。バウンディングボックスをリアルタイム描画 |
| 自動録画 | 検知時にプリイベント3秒バッファ付きで自動録画開始。検知終了後も設定秒数だけ延長録画 |
| スナップショット | 検知時に自動でJPEGスナップショットを保存 |
| 検知除外マスク | ブラウザ上のCanvasエディタで除外エリアを塗りつぶし。木の揺れや道路など不要な領域を除外 |
| LINE通知 | 動体検知時にスマホへプッシュ通知。クールダウン制御付き（デフォルト60秒） |
| ストレージ自動管理 | 7日超の古いファイルを自動削除。容量上限（デフォルト28GB）を超えた場合も古い順に削除 |
| Web UI | ライブ視聴・録画一覧/再生/削除・設定変更・マスク編集をすべてブラウザで操作 |
| Basic認証 | 全エンドポイントにbcryptベースのBasic認証を適用 |

---

## 要件

### ハードウェア

| 項目 | 最小要件 | 推奨 |
|------|----------|------|
| ボード | Raspberry Pi 3 Model B+ | Raspberry Pi 4 Model B (2GB以上) |
| カメラ | USB Webカメラ (UVC対応) | 720p以上対応のもの |
| ストレージ | 16GB microSD | 32GB microSD (Class 10 / A1以上) |
| ネットワーク | LAN接続 (有線 or Wi-Fi) | 有線LAN推奨 |

### ソフトウェア

| 項目 | バージョン |
|------|-----------|
| OS | Raspberry Pi OS (Bookworm) / Ubuntu 22.04+ / その他Linux |
| Python | 3.10 以上 |
| pip | 最新推奨 |

### Python パッケージ（`requirements.txt`）

```
opencv-python-headless>=4.9.0    # 映像処理（GUI不要版）
flask>=3.0.0                     # Webフレームワーク
PyYAML>=6.0                      # YAML設定ファイル
bcrypt>=4.1.0                    # パスワードハッシュ
numpy>=1.26.0                    # 数値計算（OpenCV依存）
line-bot-sdk>=3.10.0             # LINE Messaging API
requests>=2.31.0                 # HTTP通信
```

---

## 事前準備

### 1. Raspberry Pi の初期セットアップ

```bash
# OSアップデート
sudo apt-get update && sudo apt-get upgrade -y

# 必要なシステムパッケージ
sudo apt-get install -y python3-venv python3-dev libopencv-dev git
```

### 2. USB Webカメラの接続確認

```bash
# カメラが認識されていることを確認
lsusb
# 例: Bus 001 Device 004: ID 046d:0825 Logitech, Inc. Webcam C270

# /dev/video0 が存在するか確認
ls /dev/video*
# 例: /dev/video0

# (任意) 映像テスト
python3 -c "
import cv2
cap = cv2.VideoCapture(0)
ret, frame = cap.read()
print(f'取得成功: {ret}, 解像度: {frame.shape if ret else \"N/A\"}')
cap.release()
"
```

### 3. LINE通知の準備（任意）

LINE通知を使う場合は、事前に以下を用意してください。

1. [LINE Developers](https://developers.line.biz/) でプロバイダーとチャネル（Messaging API）を作成
2. チャネルアクセストークン（長期）を発行
3. 自分のユーザーIDを確認（チャネル基本設定 → Your user ID）

---

## インストール

### 方法A: 自動インストール（Raspberry Pi 推奨）

```bash
# リポジトリ取得
git clone <repository-url> ~/microcam
cd ~/microcam

# インストールスクリプト実行
bash scripts/install.sh
```

スクリプトが以下を自動実行します:
1. システムパッケージのインストール (`python3-venv`, `python3-dev`, `libopencv-dev`)
2. Python仮想環境 (`.venv`) の作成
3. pip依存パッケージのインストール
4. 管理パスワードの設定（対話式）
5. systemdサービスの登録・有効化

### 方法B: 手動インストール

```bash
# リポジトリ取得
git clone <repository-url>
cd microcam

# 仮想環境の作成と有効化
python3 -m venv .venv
source .venv/bin/activate          # Linux/Mac
# .venv\Scripts\activate           # Windows

# パッケージインストール
pip install --upgrade pip
pip install -r requirements.txt

# データディレクトリ作成
mkdir -p data/recordings data/snapshots
```

---

## 設定

すべての設定は `config/config.yaml` に集約されています。
Web UIの設定画面からも変更可能です（変更時はYAMLファイルに自動保存されます）。

### 設定ファイル全体

```yaml
camera:
  device: 0                  # カメラデバイス番号 (/dev/video0 = 0)
  width: 1280                # 解像度 横
  height: 720                # 解像度 縦
  fps: 15                    # フレームレート

detection:
  enabled: true              # 動体検知の有効/無効
  alpha: 0.01                # 背景学習率 (小さいほど変化に鈍感)
  threshold: 25              # 二値化閾値 (大きいほど鈍感)
  min_area: 500              # 最小輪郭面積 (px) — これ未満の動きは無視
  post_seconds: 5            # 検知後の録画延長秒数

recording:
  pre_seconds: 3             # プリイベントバッファ秒数 (検知前の映像)
  max_seconds: 300           # 1回あたりの最大録画秒数
  output_dir: data/recordings
  snapshot_dir: data/snapshots

storage:
  retention_days: 7          # 録画の保持日数
  max_gb: 28                 # 最大使用量 (GB)
  cleanup_interval: 3600     # クリーンアップ間隔 (秒)

web:
  host: "0.0.0.0"            # 全インターフェースでリッスン
  port: 8080                 # Webサーバーポート
  username: admin            # Basic認証ユーザー名
  password_hash: "..."       # bcryptハッシュ (install.shで自動生成)

line:
  enabled: false             # LINE通知の有効/無効
  channel_access_token: ""   # チャネルアクセストークン
  user_id: ""                # 送信先ユーザーID
  cooldown: 60               # 通知クールダウン (秒)

logging:
  level: INFO                # ログレベル (DEBUG / INFO / WARNING / ERROR)
```

### パスワードの手動変更

```bash
python3 -c "
import bcrypt
pw = input('新しいパスワード: ')
print(bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode())
"
# 出力されたハッシュ値を config.yaml の password_hash に貼り付け
```

### 環境変数による設定ファイルパス指定

```bash
export MICROCAM_CONFIG=/path/to/custom-config.yaml
python -m microcam
```

---

## 起動・実行

### 手動起動（開発・テスト用）

```bash
source .venv/bin/activate
python -m microcam
```

起動後、ブラウザで以下にアクセスします:
```
http://<Raspberry PiのIPアドレス>:8080
```

デフォルト認証情報:
- ユーザー名: `admin`
- パスワード: `microcam`

### systemd サービスとして起動（本番運用）

```bash
# 起動
sudo systemctl start microcam

# 停止
sudo systemctl stop microcam

# 再起動
sudo systemctl restart microcam

# ステータス確認
sudo systemctl status microcam

# ログをリアルタイムで確認
journalctl -u microcam -f

# 自動起動の有効化（install.shで設定済み）
sudo systemctl enable microcam

# 自動起動の無効化
sudo systemctl disable microcam
```

systemdサービスは `Restart=always` / `RestartSec=5` に設定されており、
プロセスが異常終了しても5秒後に自動復帰します。

---

## Web UI の使い方

### ライブ (`/live`)

- カメラ映像のリアルタイム視聴
- FPS・検知状態・録画中のステータス表示
- 「検知 ON/OFF」ボタンで動体検知を即時トグル

### 録画一覧 (`/recordings`)

- 録画ファイルの一覧表示（ファイル名・日時・サイズ）
- ブラウザ内での動画再生
- 個別削除

### 設定 (`/settings`)

- 検知パラメータ調整（学習率・閾値・最小面積・延長秒数）
- 録画設定（プリイベントバッファ・最大録画時間）
- ストレージ設定（保持日数・容量上限）+ 使用量表示
- LINE通知設定（トークン・ユーザーID・クールダウン）+ テスト通知
- パスワード変更
- 検知除外マスクエディタ（ブラシサイズ調整・クリア・保存）

---

## コマンドラインオプション

```
usage: python -m microcam [-h] [-c CONFIG] [--host HOST] [--port PORT] [--debug]

MicroCam 監視カメラシステム

options:
  -h, --help            ヘルプメッセージを表示
  -c, --config CONFIG   設定ファイルのパス (デフォルト: config/config.yaml)
  --host HOST           Webサーバーのホスト (設定ファイルを上書き)
  --port PORT           Webサーバーのポート (設定ファイルを上書き)
  --debug               デバッグモード (ログレベルをDEBUGに設定)
```

### 使用例

```bash
# デフォルト設定で起動
python -m microcam

# カスタム設定ファイルを指定
python -m microcam -c /etc/microcam/config.yaml

# ポートを変更して起動
python -m microcam --port 9090

# デバッグモードで起動
python -m microcam --debug
```

---

## REST API リファレンス

すべてのエンドポイントにBasic認証が必要です。

| メソッド | パス | 説明 |
|----------|------|------|
| GET | `/api/status` | システムステータス (カメラ稼働・FPS・検知状態・録画中) |
| POST | `/api/detection` | 検知ON/OFFトグル — Body: `{"enabled": true}` |
| GET | `/api/recordings` | 録画ファイル一覧 (JSON配列) |
| GET | `/api/recordings/<filename>` | 録画ファイルダウンロード |
| DELETE | `/api/recordings/<filename>` | 録画ファイル削除 |
| GET | `/api/snapshots/<filename>` | スナップショット取得 |
| GET | `/api/mask` | 検知除外マスク画像 (PNG) |
| PUT | `/api/mask` | 検知除外マスク保存 — Body: `{"image": "data:image/png;base64,..."}` |
| GET | `/api/config` | 現在の設定取得 (パスワードハッシュ除外) |
| PUT | `/api/config` | 設定更新 — Body: JSON (セクション単位で部分更新可) |
| GET | `/api/storage/usage` | ディスク使用量 (`total_bytes`, `file_count`) |
| POST | `/api/line/test` | LINE通知テスト送信 |

---

## スレッドアーキテクチャ

本システムは4つのバックグラウンドスレッドで構成されています。
OpenCVはI/O操作時にGILを解放するため、`threading` モジュールで十分なパフォーマンスが得られます。

```
USB Webcam
    |
    v
[Thread 1: カメラキャプチャ] ──frame──> 共有バッファ (deque)
    |                                       |
    |                                       +──> [MJPEGストリーム] ──> ブラウザ
    v
[Thread 2: 検知+録画ループ]
    |
    +── detector.process_frame()  -> 動体検知 + バウンディングボックス描画
    +── recorder.feed_frame()     -> リングバッファ / 録画書き込み
    |         |
    |         +── 検知時 -> start_recording() + capture_snapshot()
    |                               |
    v                               v
[Thread 3: 通知キュー]         [Thread 4: ストレージクリーンアップ]
    |                               |
    v                               v
LINE Messaging API              古いファイル自動削除 (1時間毎)
```

---

## フォルダ構成と各ファイルの説明

```
microcam/
├── microcam/                        メインパッケージ
│   ├── __init__.py                  パッケージ初期化、バージョン定義
│   ├── __main__.py                  エントリーポイント (引数解析・シグナルハンドラ・起動)
│   ├── app.py                       オーケストレータ (全コンポーネント統合・Flask構築・検知ループ)
│   ├── camera.py                    カメラキャプチャスレッド (フレーム共有・リングバッファ・自動再接続)
│   ├── detector.py                  動体検知エンジン (背景差分・閾値・輪郭フィルタ・マスク適用・BB描画)
│   ├── recorder.py                  録画管理 (プリイベントバッファ・VideoWriter・スナップショット保存)
│   ├── notifier.py                  LINE通知 (キュー+ワーカースレッド・クールダウン制御)
│   ├── storage.py                   ストレージ管理 (日数超過削除・容量上限制御・使用量計算)
│   ├── config.py                    設定ロード/保存 (YAML⇔データクラス変換)
│   ├── auth.py                      Basic認証 (bcrypt検証・デコレータ・パスワードハッシュ生成)
│   ├── streaming.py                 MJPEGストリームジェネレータ (JPEG圧縮・multipart配信)
│   └── web/
│       ├── __init__.py              Webサブパッケージ初期化
│       ├── routes.py                Flaskページルート (/, /live, /recordings, /settings, /video_feed)
│       ├── api.py                   REST APIエンドポイント (/api/status, /api/recordings, etc.)
│       ├── static/
│       │   ├── css/style.css        UIスタイルシート (ダークテーマ・レスポンシブ対応)
│       │   └── js/
│       │       ├── app.js           フロントエンド共通 (ステータス更新・検知トグル)
│       │       └── mask_editor.js   検知除外エリアCanvas描画ツール (マウス/タッチ対応)
│       └── templates/
│           ├── base.html            共通テンプレート (ナビゲーションバー・レイアウト)
│           ├── live.html            ライブ映像ページ (MJPEGストリーム・ステータスバー)
│           ├── recordings.html      録画一覧ページ (再生・削除)
│           └── settings.html        設定ページ (全パラメータ・マスクエディタ・LINE設定)
├── config/
│   └── config.yaml                  デフォルト設定ファイル (全パラメータにコメント付き)
├── data/                            実行時データ (自動生成・.gitignore対象)
│   ├── recordings/                  録画ファイル格納ディレクトリ (MP4)
│   ├── snapshots/                   スナップショット格納ディレクトリ (JPEG)
│   └── mask.png                     検知除外マスク画像 (白=検知対象・黒=除外)
├── scripts/
│   ├── install.sh                   Raspberry Piセットアップスクリプト (venv・pip・systemd一括設定)
│   └── microcam.service             systemdユニットファイル (Restart=always, RestartSec=5)
├── tests/
│   ├── test_config.py               config.pyのテスト (ロード・デフォルト・部分設定・保存・絶対パス)
│   ├── test_detector.py             detector.pyのテスト (初期化・静止・動体・小面積・マスク除外)
│   ├── test_recorder.py             recorder.pyのテスト (開始/停止・プリイベント・スナップショット)
│   └── test_storage.py              storage.pyのテスト (使用量・日数超過削除・容量超過削除)
├── requirements.txt                 Python依存パッケージ一覧
├── .gitignore                       Git除外設定 (data/・__pycache__・.venv・ログ・証明書)
└── README.md                        本ファイル
```

### 各モジュールの詳細

#### `__main__.py` — エントリーポイント
`python -m microcam` で呼ばれるメイン関数。コマンドライン引数の解析、ログ設定、シグナルハンドラ（`SIGTERM` / `SIGINT`）の登録を行い、`MicroCamApp` を起動します。

#### `app.py` — オーケストレータ
システム全体のライフサイクルを管理する中心モジュールです。`start()` でカメラ・検知・録画・通知・ストレージの全コンポーネントを初期化・起動し、`run()` でFlask Webサーバーを開始します。検知ループスレッドではカメラからフレームを取得し、動体検知→録画→通知の一連の処理を実行します。

#### `camera.py` — カメラキャプチャ
専用スレッドでUSBカメラからフレームを取得し、ロック付き共有バッファに格納します。カメラ切断時は自動再接続を試みます。`deque` ベースのリングバッファでプリイベント用のフレーム履歴も保持します。

#### `detector.py` — 動体検知エンジン
`cv2.accumulateWeighted()` による適応的背景モデルを使用。差分画像→二値化→膨張処理→輪郭検出→面積フィルタの順で動体を判定します。検知時はフレームにバウンディングボックスと「MOTION DETECTED」テキストを直接描画します。除外マスク（PNG）の読み込みとリアルタイム適用にも対応。

#### `recorder.py` — 録画・スナップショット
`cv2.VideoWriter`（mp4vコーデック）で録画を行います。録画開始時にリングバッファのフレーム（プリイベント3秒分）を先に書き込むことで、検知直前の映像も記録します。スナップショットはJPEG品質85で保存。

#### `notifier.py` — LINE通知
`queue.Queue` + ワーカースレッドのパターンで、検知ループをブロックせずに非同期で通知を送信します。クールダウン制御により、短時間に大量の通知が飛ぶのを防止します。

#### `storage.py` — ストレージ管理
バックグラウンドスレッドで1時間ごとにクリーンアップを実行。保持日数を超えたファイルの削除と、合計容量が上限を超えた場合の古い順からの削除を行います。

#### `config.py` — 設定管理
YAMLファイルをデータクラス群にマッピングします。未知のキーは安全に無視し、設定ファイルが存在しない場合はデフォルト値で動作します。`save_config()` で実行中の設定変更をYAMLに書き戻すことも可能です。

#### `auth.py` — 認証
bcryptハッシュによるパスワード検証と、Flask `before_request` フックで全エンドポイントに適用されるBasic認証を提供します。

#### `streaming.py` — MJPEG配信
カメラの共有バッファから最新フレームを取得し、JPEG圧縮（品質70）して `multipart/x-mixed-replace` 形式で連続配信するジェネレータです。

---

## テスト

```bash
# テスト実行
source .venv/bin/activate
pip install pytest
pytest tests/ -v
```

### テストカバレッジ

| テストファイル | テスト数 | 対象 |
|----------------|----------|------|
| `test_config.py` | 5 | 設定ロード・デフォルト値・部分設定・保存・パス解決 |
| `test_detector.py` | 5 | 初期化・静止シーン・動体検知・小面積無視・マスク除外 |
| `test_recorder.py` | 5 | 開始/停止・プリイベントバッファ・スナップショット・安全性 |
| `test_storage.py` | 4 | 使用量計算・日数超過削除・容量超過削除・空ディレクトリ |

テストはカメラデバイス不要で、合成フレーム（NumPy配列）と一時ディレクトリを使って実行されます。

---

## トラブルシューティング

### カメラが認識されない

```bash
# デバイスの確認
ls /dev/video*
# v4l2-utils で詳細確認
v4l2-ctl --list-devices
```

`config.yaml` の `camera.device` が正しいデバイス番号か確認してください。
複数カメラがある場合は `0`, `2`, `4` ... のように偶数番号を試してください。

### ブラウザでライブ映像が表示されない

- Raspberry Pi のIPアドレスとポートが正しいか確認
- ファイアウォールでポート8080が開放されているか確認: `sudo ufw allow 8080`
- Basic認証のユーザー名・パスワードが正しいか確認

### 録画ファイルが再生できない

mp4vコーデックは一部のプレーヤーで非対応です。VLC Media Player での再生を推奨します。

### LINE通知が届かない

- `config.yaml` の `line.enabled` が `true` か確認
- チャネルアクセストークンとユーザーIDが正しいか確認
- Web UIの設定画面から「テスト通知」ボタンで送信テスト
- ログ確認: `journalctl -u microcam -f | grep LINE`

### ディスクが満杯

ストレージクリーンアップは1時間間隔で実行されます。緊急時は手動で古い録画を削除してください。
```bash
# 古い録画を手動削除
find data/recordings/ -mtime +3 -delete
```

---

## 次回に向けた改善ポイント

### 映像品質・パフォーマンス

- [ ] **H.264コーデック対応**: `ffmpeg` をサブプロセスで呼び出し、mp4vから H.264/H.265 に変更。ファイルサイズ削減とブラウザ互換性向上
- [ ] **HLS配信への移行**: MJPEG → HLS (`m3u8` + `ts` セグメント) に変更し、遅延と帯域を削減。モバイル対応も向上
- [ ] **GPU/ハードウェアエンコーディング**: Raspberry Pi 4 の V4L2 M2M エンコーダ活用
- [ ] **解像度の動的切り替え**: ネットワーク帯域に応じた品質自動調整

### 検知精度

- [ ] **MOG2 / KNN背景差分**: OpenCVの `createBackgroundSubtractorMOG2()` に切り替え、照明変化・影への耐性向上
- [ ] **ゾーン別感度設定**: 画面領域ごとに異なる閾値・面積を設定可能に
- [ ] **時間帯別検知設定**: 夜間は感度を上げる、昼間は特定エリアのみなどのスケジュール対応
- [ ] **物体追跡**: 検知した物体にIDを割り当て、移動経路を記録

### セキュリティ

- [ ] **HTTPS対応**: Let's Encrypt 自動取得 or 自己署名証明書。現在はHTTP平文通信のため、LAN外公開は危険
- [ ] **セッション認証**: Basic認証 → Flask-Login + セッションベースに変更。ログアウト機能追加
- [ ] **レート制限**: ログイン試行回数の制限（ブルートフォース対策）
- [ ] **APIキー認証**: REST API向けの独立した認証メカニズム

### 通知・連携

- [ ] **画像付きLINE通知**: スナップショットをクラウドストレージにアップロードし、URLで送信
- [ ] **Webhook連携**: 検知イベントを任意のURL (Discord, Slack, IFTTT等) にPOST
- [ ] **メール通知**: SMTP経由でのメール通知対応
- [ ] **通知スケジュール**: 特定の時間帯のみ通知する「おやすみモード」

### Web UI

- [ ] **WebSocket対応**: ステータス更新をポーリング → WebSocket でリアルタイムに
- [ ] **タイムライン表示**: 検知イベントを時系列で可視化
- [ ] **複数カメラ対応**: 複数のUSBカメラを切り替え・同時表示
- [ ] **PWA化**: Service Worker + マニフェストでスマホのホーム画面に追加可能に
- [ ] **録画のサムネイル生成**: 一覧で先頭フレームをサムネイル表示

### インフラ・運用

- [ ] **Docker対応**: `Dockerfile` + `docker-compose.yml` でワンコマンドデプロイ
- [ ] **gunicorn / uWSGI**: Flask組み込みサーバーから本格WSGIサーバーに移行（同時接続数向上）
- [ ] **ログローテーション**: `logrotate` 設定で長期運用時のログ肥大化を防止
- [ ] **ヘルスチェックAPI**: `/api/health` エンドポイントで外部監視ツール連携
- [ ] **メトリクス収集**: Prometheus エクスポーターで CPU・メモリ・FPS・検知数を可視化

---

## 運用面のネクストアクション

### 導入直後（1週間以内）

1. **パスワードを必ず変更する** — デフォルトパスワード (`microcam`) は公開されているため、初回起動後すぐにWeb UIの設定画面またはCLIで変更してください
2. **カメラの画角を調整する** — 監視対象が映像の中央に映るよう物理的な設置位置を調整
3. **検知パラメータを調整する** — 設置環境に合わせて `threshold`（閾値）と `min_area`（最小面積）をWeb UIで微調整。風で揺れる木や往来の多い道路が映り込む場合は除外マスクを設定
4. **ストレージ消費量を監視する** — 1日あたりの録画量を確認し、`retention_days` と `max_gb` を環境に合った値に調整

### 安定稼働確認後（1ヶ月以内）

5. **LINE通知を設定する** — LINE Developers でチャネルを作成し、設定画面からトークン・ユーザーIDを登録。テスト通知で疎通確認
6. **自己署名SSL証明書を導入する** — LAN内でも通信を暗号化したい場合は以下を実行:
   ```bash
   openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem -days 365 -nodes
   ```
7. **バックアップ計画を策定する** — 設定ファイル (`config/config.yaml`) と除外マスク (`data/mask.png`) を定期的にバックアップ
8. **systemdサービスの動作を確認する** — `kill` コマンドでプロセスを停止し、5秒後に自動復帰することを確認

### 長期運用（3ヶ月以降）

9. **SDカードの寿命に注意する** — 録画の書き込み頻度が高い場合、SDカードの寿命が短くなります。USB接続のSSD/HDDへの録画先変更を検討
10. **Raspberry Pi OSのアップデートを定期実行する** — セキュリティパッチの適用
11. **ログの定期確認** — `journalctl -u microcam --since "1 week ago"` でエラーや警告を確認
12. **検知パラメータの季節調整** — 照明条件の変化（夏/冬の日照時間差）に応じて `alpha` や `threshold` を微調整
