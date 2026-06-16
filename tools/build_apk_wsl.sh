#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/mnt/c/Users/liaolibing/Desktop/pierre/综合课程设计/FloatMask"
cd "$PROJECT_DIR"

sudo apt-get update
sudo apt-get install -y \
  git zip unzip openjdk-17-jdk python3-pip python3-venv python3-setuptools curl \
  autoconf libtool pkg-config zlib1g-dev libncurses5-dev libncursesw5-dev \
  libtinfo6 cmake libffi-dev libssl-dev

if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
export PATH="$HOME/.local/bin:$PATH"
export JAVA_HOME=/usr/lib/jvm/java-1.17.0-openjdk-amd64
export JDK_HOME=$JAVA_HOME
export PATH="$JAVA_HOME/bin:$PATH"
uv python install 3.11
uv venv --python 3.11 --seed --clear "$HOME/.venvs/floatmask-build"
# shellcheck disable=SC1091
source "$HOME/.venvs/floatmask-build/bin/activate"
python -m pip install --upgrade "pip<25" "setuptools<70" "wheel<0.44"
python -m pip install "buildozer==1.5.0" "cython==0.29.37" "virtualenv<21"

buildozer -v android debug

mkdir -p dist
APK_PATH="$(ls -t bin/*.apk | head -n 1)"
cp "$APK_PATH" dist/FloatMask.apk
printf '\nAPK generated: %s\n' "$PROJECT_DIR/dist/FloatMask.apk"
