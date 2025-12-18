@echo off
setlocal
cd /d %~dp0\..

REM One-time:
REM   py -m pip install --upgrade pip
REM   py -m pip install pyinstaller

py -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --onefile ^
  --windowed ^
  --name YMCA_Card_Maker ^
  src\ymca_card_maker_gui.py

echo.
echo Built EXE:
echo   dist\YMCA_Card_Maker.exe
echo.
pause
