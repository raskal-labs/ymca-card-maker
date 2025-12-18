# Build a Windows EXE

This project uses Tkinter for the GUI, so PyInstaller can produce a double-clickable EXE.

## Install
```powershell
py -m pip install --upgrade pip
py -m pip install pyinstaller
```

## Build
From repo root:
```powershell
.\tools\build_exe_windows.bat
```

## Output
- `dist\YMCA_Card_Maker.exe`

Keep the EXE in the same folder as the repo, or keep:
- `src/ymca_card_maker.py`
available. The GUI auto-detects it.
