@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

where python >nul 2>&1
if errorlevel 1 goto no_python

python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"
if errorlevel 1 goto old_python

if not exist ".venv\Scripts\python.exe" (
  echo Создание виртуального окружения .venv ...
  python -m venv .venv
  if errorlevel 1 goto venv_fail
)

echo Проверка зависимостей...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto pip_fail

echo Запуск калькулятора...
".venv\Scripts\python.exe" main.py
if errorlevel 1 goto run_fail
exit /b 0

:no_python
echo [Ошибка] Python не найден в PATH.
echo Установите Python 3.10 или новее с python.org
echo и включите пункт "Add python.exe to PATH".
goto fail

:old_python
echo [Ошибка] Нужен Python 3.10 или новее.
python --version
goto fail

:venv_fail
echo [Ошибка] Не удалось создать виртуальное окружение.
goto fail

:pip_fail
echo [Ошибка] Не удалось установить зависимости из requirements.txt.
echo Проверьте подключение к интернету и повторите запуск.
goto fail

:run_fail
echo [Ошибка] Программа завершилась с ошибкой.
goto fail

:fail
echo.
pause
exit /b 1
