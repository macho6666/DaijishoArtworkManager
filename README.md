# Daijisho Artwork Manager v0.1

목표
- USB/ADB로 휴대폰 ROM 폴더를 직접 읽음
- 이미지가 없거나 바꿀 게임을 체크
- Google 이미지 검색(브라우저) 또는 Google Custom Search API 후보를 앱 안에 표시
- PC의 이미지를 직접 선택 가능
- PNG/WEBP/JPEG/BMP/TIFF 등을 JPG로 자동 변환
- ROM 파일명과 동일한 이름으로 변경 (확장자만 .jpg)
- `/sdcard/DaijishoMedia/<플랫폼>/`에 ADB로 자동 전송

예:
`Hokuto no Ken (K).zip` -> `Hokuto no Ken (K).jpg`

## 준비
1. Android에서 개발자 옵션 > USB 디버깅 켜기
2. Google Android Platform Tools 설치
3. `adb.exe`가 PATH에 있거나, 빌드된 EXE와 같은 폴더에 `adb.exe`, `AdbWinApi.dll`, `AdbWinUsbApi.dll` 배치
4. 휴대폰 연결 후 "이 컴퓨터에서 USB 디버깅 허용" 승인

## 실행
Python 3.11+:
```
pip install -r requirements.txt
python app.py
```

## Google 이미지
- `Google 이미지 검색`: 별도 API 없이 기본 브라우저에서 해당 게임 + 플랫폼 + box art 검색.
  원하는 이미지를 PC에 저장한 뒤 `내 이미지 선택`으로 가져오면 됨.
- `앱 안에서 Google 후보 검색`: Google Programmable Search / Custom Search JSON API의 API Key와 Search Engine ID(cx)가 필요.
  프로그램의 `Google API 설정`에 입력. 키는 사용자 PC의 홈 폴더 `.daijisho_artwork_manager.json`에 저장됨.
- 웹페이지 HTML을 억지로 스크래핑하지 않으므로 Google 화면 변경에 덜 취약함.

## Daijisho에서 마지막 작업
전송 후 Daijisho의 해당 플랫폼 편집에서:
`박스 아트용 미리보기 미디어 불러오기` -> `/DaijishoMedia/<플랫폼>` 선택.

Daijisho가 이미지를 가져간 뒤 원본 DaijishoMedia 이미지는 필요에 따라 정리할 수 있음(먼저 표시 유지 확인 권장).

## 플랫폼 기본 경로
GB `/sdcard/Roms/GB` -> `/sdcard/DaijishoMedia/GB`
GBC `/sdcard/Roms/GBC` -> `/sdcard/DaijishoMedia/GBC`
GBA `/sdcard/Roms/GBA` -> `/sdcard/DaijishoMedia/GBA`
NES `/sdcard/Roms/NES` -> `/sdcard/DaijishoMedia/NES`
NDS `/sdcard/Roms/NDS` -> `/sdcard/DaijishoMedia/NDS`
SNES `/sdcard/Roms/SNES` -> `/sdcard/DaijishoMedia/SNES`
Genesis `/sdcard/Roms/MD` -> `/sdcard/DaijishoMedia/Genesis`

실제 폴더가 다르면 프로그램의 `경로 설정`에서 변경.

## v0.1 참고
- Windows 탐색기의 MTP 경로를 직접 다루지 않고 ADB를 사용함.
- 드래그앤드롭은 안내 문구만 있고 v0.1에는 아직 구현하지 않음. `내 이미지 선택`은 완전 동작.
- Google 후보 이미지는 원본 서버가 외부 다운로드를 차단하면 일부 후보가 안 보일 수 있음.


## GitHub Actions에서 Python 없이 Windows EXE 만들기

1. 새 GitHub 저장소를 만들고 이 ZIP의 **내용물 전체**를 저장소 루트에 업로드합니다.
   `.github/workflows/build-windows.yml`도 반드시 포함되어야 합니다.
2. GitHub의 **Actions** 탭에서 `Build Windows EXE`를 엽니다.
3. `Run workflow`를 누릅니다. main 브랜치에 파일을 올려도 자동 빌드됩니다.
4. 빌드가 끝나면 실행 결과 페이지 아래 **Artifacts**에서
   `DaijishoArtworkManager-Windows`를 다운로드합니다.
5. 압축을 풀면 `DaijishoArtworkManager.exe`가 있습니다.

PC에는 Python을 설치할 필요가 없습니다.

### ADB 주의
프로그램이 휴대폰에 접근하려면 `adb.exe`가 필요합니다.
Android Platform Tools의 `adb.exe`, `AdbWinApi.dll`, `AdbWinUsbApi.dll`을
EXE와 같은 폴더에 두거나 Windows PATH에 ADB를 등록하세요.
