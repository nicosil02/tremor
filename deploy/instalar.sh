#!/usr/bin/env bash
# Tremor en una máquina propia (Oracle Cloud "always free", Ubuntu 22.04 ARM, 4 núcleos y 24 GB): radio en vivo 24 horas.
#   curl -fsSL https://raw.githubusercontent.com/nicosil02/tremor/main/deploy/instalar.sh | bash -s -- Bateas
# Después: copiar el .env (claves del LLM y de Telegram) a ~/tremor/.env y `sudo systemctl restart tremor-vivo`.
set -euo pipefail
EMPRESA="${1:-Bateas}"
sudo apt-get update -q && sudo apt-get install -y -q ffmpeg git python3-venv python3-pip
cd ~ && { [ -d tremor ] && git -C tremor pull -q || git clone -q https://github.com/nicosil02/tremor; }
cd ~/tremor && python3 -m venv .venv && . .venv/bin/activate
pip install -q --upgrade pip && pip install -q -r requirements.txt faster-whisper
mkdir -p datos && [ -f datos/tremor.db ] || { git fetch -q origin datos && git show origin/datos:tremor.db.gz | gunzip > datos/tremor.db; }
[ -f .env ] || cp .env.example .env   # pegar aquí LLM_API_KEY, GEMINI_API_KEY, TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID
sudo tee /etc/systemd/system/tremor-vivo.service >/dev/null <<UNIT
[Unit]
Description=Tremor: radio en vivo para $EMPRESA
After=network-online.target
[Service]
User=$USER
WorkingDirectory=$HOME/tremor
EnvironmentFile=$HOME/tremor/.env
ExecStart=$HOME/tremor/.venv/bin/python -m tremor.radio vivo --empresa $EMPRESA --hilos 4
Restart=always
RestartSec=30
[Install]
WantedBy=multi-user.target
UNIT
sudo systemctl daemon-reload && sudo systemctl enable --now tremor-vivo
echo "Listo. Ver el log en vivo: journalctl -u tremor-vivo -f"
