#!/usr/bin/env bash
# Запуск калькулятора PoE на Ubuntu. Двойной щелчок или ./run_ubuntu.sh
set -euo pipefail

cd "$(dirname "$(readlink -f "$0")")"

fail() {
  echo
  echo "[Ошибка] $*"
  echo
  echo "Нажмите Enter, чтобы закрыть окно..."
  read -r _ || true
  exit 1
}

if ! command -v python3 >/dev/null 2>&1; then
  fail "Команда python3 не найдена. Установите Python 3.10 или новее: sudo apt install python3"
fi

if ! python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'; then
  fail "Нужен Python 3.10 или новее. Сейчас: $(python3 --version 2>&1)"
fi

if [[ ! -x .venv/bin/python ]]; then
  echo "Создание виртуального окружения .venv ..."
  if ! python3 -m venv .venv; then
    fail "$(cat <<'EOF'
Не удалось создать виртуальное окружение.
Обычно не установлен пакет python3-venv.
Установите его и запустите файл ещё раз:
  sudo apt install python3-venv
Если пакет разбит по версиям интерпретатора, например:
  sudo apt install python3.12-venv
EOF
)"
  fi
fi

echo "Проверка зависимостей..."
if ! .venv/bin/python -m pip install --disable-pip-version-check -r requirements.txt; then
  fail "Не удалось установить зависимости из requirements.txt. Проверьте интернет и повторите запуск."
fi

echo "Запуск калькулятора..."
set +e
.venv/bin/python main.py
status=$?
set -e
if [[ $status -ne 0 ]]; then
  fail "Программа завершилась с кодом ${status}."
fi
