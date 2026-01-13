#!/bin/bash

set -e

echo "=== [Reco Setup Script] ==="

# Detect OS family
OS_FAMILY=$(grep -Ei 'debian|ubuntu' /etc/*release > /dev/null && echo "debian" || echo "rhel")

# Step 1: Ensure Python 3 is installed
if ! command -v python3 &>/dev/null; then
    echo "[*] Python3 not found. Installing..."
    if [ "$OS_FAMILY" == "debian" ]; then
        sudo apt update && sudo apt install -y python3
    else
        sudo yum install -y python3
    fi
else
    echo "[*] Python3 is already installed."
fi

# Step 2: Detect exact version like 3.12
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "[*] Detected Python version: $PYTHON_VERSION"

# Step 3: Install venv support
echo "[*] Installing python-venv..."
if [ "$OS_FAMILY" == "debian" ]; then
    sudo apt install -y python3-venv python${PYTHON_VERSION}-venv
else
    sudo yum install -y python3-venv || true
fi

# Step 4: Ensure cron is available
if ! command -v crontab &>/dev/null; then
    echo "[*] Installing crontab support..."
    if [ "$OS_FAMILY" == "debian" ]; then
        sudo apt install -y cron
        sudo systemctl enable --now cron
    else
        sudo yum install -y cronie
        sudo systemctl enable --now crond
    fi
fi

# Step 5: Create virtual environment
VENV_DIR="./venv"
if [ -d "$VENV_DIR" ]; then
    echo "[*] Removing old virtual environment..."
    rm -rf "$VENV_DIR"
fi
echo "[*] Creating virtual environment..."
python3 -m venv "$VENV_DIR"

# Step 6: Install Python packages
echo "[*] Installing pip packages..."
"$VENV_DIR/bin/pip" install --upgrade pip
"$VENV_DIR/bin/pip" install pyyaml requests

# Step 7: Parse cron expressions
CONFIG_PATH="./config.yaml"
if [ ! -f "$CONFIG_PATH" ]; then
    echo "[!] ERROR: config.yaml not found."
    exit 1
fi

POSTURE_CRON=$("$VENV_DIR/bin/python" -c "import yaml; print(yaml.safe_load(open('$CONFIG_PATH')).get('posture', {}).get('cron', ''))")
ALERTS_CRON=$("$VENV_DIR/bin/python" -c "import yaml; print(yaml.safe_load(open('$CONFIG_PATH')).get('alerts', {}).get('cron', ''))")

if [[ -z "$POSTURE_CRON" || -z "$ALERTS_CRON" ]]; then
    echo "[!] ERROR: Missing cron values in config.yaml"
    exit 1
fi

echo "[*] Posture cron: $POSTURE_CRON"
echo "[*] Alerts cron:  $ALERTS_CRON"

# Step 8: Update crontab
echo "[*] Updating crontab..."
BIN_PYTHON=$(realpath "$VENV_DIR/bin/python")
POSTURE_PY=$(realpath posture.py)
ALERTS_PY=$(realpath alerts.py)

crontab -l 2>/dev/null | grep -v "# posture_job" | grep -v "# alerts_job" > new_crontab || true
echo "$POSTURE_CRON $BIN_PYTHON $POSTURE_PY # posture_job" >> new_crontab
echo "$ALERTS_CRON $BIN_PYTHON $ALERTS_PY # alerts_job" >> new_crontab
crontab new_crontab
rm new_crontab

echo "[✅] Successfully scheduled posture.py and alerts.py via cron."
