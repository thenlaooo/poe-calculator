#!/usr/bin/env bash
# Сборка калькулятора PoE для Linux (x86-64). Результат: dist/linux/PoECalculator
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

echo "Установка зависимостей и PyInstaller..."
if ! .venv/bin/python -m pip install --disable-pip-version-check -r requirements.txt pyinstaller; then
  fail "Не удалось установить зависимости или PyInstaller. Проверьте интернет и повторите запуск."
fi

echo "Сборка dist/linux/PoECalculator ..."
if ! .venv/bin/python -m PyInstaller --noconfirm --clean --distpath dist/linux --workpath build/linux PoECalculator.spec; then
  fail "PyInstaller не собрал исполняемый файл."
fi

echo
echo "Готово: dist/linux/PoECalculator"
echo "Запустите: ./dist/linux/PoECalculator"