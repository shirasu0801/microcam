#!/bin/bash
set -e

echo "=== MicroCam インストールスクリプト ==="

# 依存パッケージ
echo "[1/5] システムパッケージをインストール..."
sudo apt-get update
sudo apt-get install -y python3-venv python3-dev libopencv-dev

# venv作成
echo "[2/5] Python仮想環境を作成..."
INSTALL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$INSTALL_DIR"

python3 -m venv .venv
source .venv/bin/activate

# pip依存
echo "[3/5] Pythonパッケージをインストール..."
pip install --upgrade pip
pip install -r requirements.txt

# デフォルトパスワードハッシュ生成
echo "[4/5] 初期設定..."
python3 -c "
import bcrypt
pw = input('管理パスワードを入力 (デフォルト: microcam): ') or 'microcam'
h = bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()
print(f'password_hash: {h}')

import yaml
with open('config/config.yaml') as f:
    cfg = yaml.safe_load(f)
cfg['web']['password_hash'] = h
with open('config/config.yaml', 'w') as f:
    yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True)
print('設定ファイルを更新しました')
"

# データディレクトリ
mkdir -p data/recordings data/snapshots

# systemd登録
echo "[5/5] systemdサービスを登録..."
sudo cp scripts/microcam.service /etc/systemd/system/
sudo sed -i "s|/home/pi/microcam|$INSTALL_DIR|g" /etc/systemd/system/microcam.service
sudo sed -i "s|User=pi|User=$(whoami)|g" /etc/systemd/system/microcam.service
sudo sed -i "s|Group=pi|Group=$(id -gn)|g" /etc/systemd/system/microcam.service
sudo systemctl daemon-reload
sudo systemctl enable microcam

echo ""
echo "=== インストール完了 ==="
echo "起動: sudo systemctl start microcam"
echo "状態: sudo systemctl status microcam"
echo "ログ: journalctl -u microcam -f"
