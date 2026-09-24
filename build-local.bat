@echo off
python -m pip install --upgrade pip
pip install -r requirements.txt
pyinstaller --noconfirm --clean --onefile --windowed --name DaijishoArtworkManager --collect-all PIL --collect-all webview app.py
pause
