@echo off
chcp 65001 >nul
python -m pip install -r requirements.txt
python -m PyInstaller --noconfirm --clean --onefile --windowed --name DaijishoArtworkManager app.py
echo.
echo EXE: dist\DaijishoArtworkManager.exe
pause
