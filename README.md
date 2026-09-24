# Daijisho Artwork Manager v0.6

Windows PC에서 Android 휴대폰의 ROM 폴더를 ADB로 읽고,
게임별 박스아트를 선택하여 Daijisho용 JPG로 변환/전송하는 도구입니다.

## v0.6 주요 기능
- 블랙 & 화이트 UI
- 실행 시 ROM 경로 `/sdcard`에서 시작
- 휴대폰 폴더 GUI 탐색/선택
- 선택한 ROM 폴더의 일반 파일 자동 목록화
- ROM 폴더명을 기반으로 `/sdcard/DaijishoMedia/<폴더명>` 자동 설정
- ROM 파일명을 검색용으로 정리하고 플랫폼명을 보정
- 내장 Google 이미지 검색 창에서 이미지 선택
- 직접 이미지 파일 선택 지원
- 선택 이미지를 JPG로 변환
- ROM 원본 파일명과 동일한 stem으로 JPG 저장
- ADB를 통해 휴대폰으로 전송

## GitHub Actions 빌드
저장소에 아래 구조로 업로드한 뒤 Commit 하면 Windows EXE가 자동 빌드됩니다.

```
app.py
requirements.txt
README.md
.gitignore
.github/
  workflows/
    build-windows.yml
```

Actions > Build Windows EXE > Artifacts에서
`DaijishoArtworkManager-Windows`를 다운로드하세요.

## 휴대폰 준비
1. Android 개발자 옵션 활성화
2. USB 디버깅 활성화
3. USB 연결 후 PC 디버깅 허용
4. PC에서 `adb devices`로 연결 확인

## ADB
프로그램은 다음 순서로 ADB를 찾습니다.
1. EXE와 같은 폴더의 `adb.exe`
2. Windows PATH에 등록된 `adb`

따라서 ADB가 PATH에 없다면 Android Platform Tools의
`adb.exe`, `AdbWinApi.dll`, `AdbWinUsbApi.dll`을 EXE와 같은 폴더에 두세요.

## 이미지 저장 예
ROM:
`/sdcard/GB/Pokemon Red (K200316 color).gb`

이미지:
`/sdcard/DaijishoMedia/GB/Pokemon Red (K200316 color).jpg`

Daijisho에서는 해당 플랫폼의 미리보기 미디어 가져오기 기능으로
`DaijishoMedia/GB` 폴더를 지정하면 됩니다.

## 참고
내장 Google 이미지 선택 기능은 Google 페이지 구조에 영향을 받을 수 있습니다.
문제가 생기면 `브라우저에서 Google 열기` 또는 `내 이미지 선택`을 사용할 수 있습니다.
