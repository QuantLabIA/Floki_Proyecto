#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

if [ ! -x ".venv/bin/python" ]; then
  echo "Creando entorno de Floki Manager..."
  python3 -m venv .venv
fi

source .venv/bin/activate

if [ ! -f ".venv/.floki_deps_v2_5" ]; then
  echo "Instalando dependencias por única vez..."
  python -m pip install -r requirements.txt
  touch .venv/.floki_deps_v2_5
fi

python run.py
