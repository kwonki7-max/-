# Windows 직원용 프로그램

기준실은 **회사에서 함께 사용하는 Windows 데스크톱 프로그램**입니다. 직원은 설치파일 실행 → 바탕화면 아이콘 실행 → 회원가입/로그인 순서로 사용합니다. 로컬 작업 공간이나 서버 주소 입력 선택지는 없습니다.

- Windows 10/11 x64 대상, Electron 45.1.0 기반 독립 창
- 앱 아이콘, 창 이동·최소화·최대화·종료, 트레이 열기/숨기기/종료
- 직원별 로그인·관리자 가입 승인·공통 견적조건 공동 편집·견적 계산·저장·CSV 다운로드
- 회사 연결은 배포 담당자가 설치파일을 만들 때 한 번 설정합니다.
- 자료는 공통 서버에 저장합니다. 앱 제거가 회사 자료를 삭제하지 않습니다.

## 현재 설치본의 상태

`dist/Gijunsil-Setup-0.1.0-x64.exe`는 서버 연결 전 빌드입니다. 설치 후 앱을 열 수 있지만, 실제 회사 서버가 아직 없으므로 **로그인·직원 간 자료 공유는 사용할 수 없습니다.** 연결 설정이 없는 경우 안내 화면을 표시하며 가짜 로그인을 제공하지 않습니다.

코드서명 인증서가 아직 없어 설치파일은 서명되지 않았습니다. 회사 배포 전 Windows 실기기 설치/제거 검증과 게시자 코드서명이 필요합니다. Linux에서 데스크톱 동작을 검증한 결과를 Windows 실기기 검증으로 간주하지 마세요.

## 서버 연결 후 회사용 설치본 만들기

Node.js 24 LTS와 npm을 설치한 빌드 컴퓨터에서:

```bash
npm ci
node scripts/configure-company.cjs https://실제회사서버주소 회사명
npm run test:desktop
npm run build:windows
```

직원들에게는 생성된 EXE만 전달하면 됩니다. 직원 PC에 Node.js나 Python을 설치할 필요가 없습니다. 서버 주소에는 HTTPS origin만 허용합니다. 계정정보·쿼리·경로는 넣지 않습니다. 회사 연결은 `desktop/company-config.json`에 저장되며 비밀번호나 토큰은 넣지 않습니다.

NSIS 사용자별 설치로 관리자 권한을 요구하지 않습니다. 기본 설치 위치는 `%LOCALAPPDATA%\Programs\Gijunsil`이고 시작 메뉴·바탕화면 바로가기를 만듭니다. 앱이 실행 중이면 설치/제거 전에 종료하도록 안내합니다. 제거할 파일은 빌드 시 생성한 목록으로 제한하며 사용자 프로필이나 알 수 없는 파일은 재귀 삭제하지 않습니다.

`desktop/installer.nsi`는 NSIS의 공식 custom-script 경로를 이용합니다. 설치 시 `WriteUninstaller`를 생성하므로 Linux 빌드 중 Windows 프로그램을 실행할 필요가 없습니다. Electron/NSIS 배포물과 npm 패키지 검증은 유지합니다.

## 개발 / 검증

```bash
npm ci
npm start
npm run test:desktop
.venv/bin/python -m pytest -q
python3 tests/desktop_smoke.py
```

마지막 명령은 Python Playwright가 설치된 Linux 환경에서 실제 Electron을 실행합니다. 임시 서버·DB·계정만 사용합니다. 이 CI 컨테이너는 SUID 설정을 제공하지 않아 테스트 프로세스에만 `--no-sandbox`를 지정하고 트레이를 생략합니다. 직원용 설치본에는 이 옵션을 넣지 않으며 `sandbox: true`, `contextIsolation: true`, `nodeIntegration: false`를 사용합니다. 개발 테스트에만 loopback HTTP를 허용하며 패키징된 앱은 HTTPS 회사 주소만 허용합니다.

회사 서버와 다른 출처로의 이동/팝업/외부 요청, 카메라·마이크 권한은 차단됩니다. Electron renderer에는 창 제어와 재연결만 노출하며 파일 시스템이나 shell 실행 기능을 노출하지 않습니다.

Windows CI는 `.github/workflows/windows.yml`의 수동 실행으로 설치본 생성과 설치/실행/제거 검증을 수행합니다. 현재 작업에서는 CI를 원격 실행하지 않았습니다.

## 실제 공동 사용까지 남은 것

1. 소유자 명의의 클라우드 서버와 도메인을 마련합니다. 요금제 가입이나 결제는 아직 수행하지 않았습니다.
2. [서버 배포 안내](SERVER.md)에 따라 HTTPS 서버와 영구 저장소를 구성하고 관리자 계정을 생성합니다.
3. 실제 주소를 설정하여 설치파일을 다시 빌드하고 Windows에서 검증합니다.
4. 직원 가입을 관리자가 승인하면 모두 같은 자료를 사용할 수 있습니다.

자동 업데이트는 아직 구현하지 않았습니다. 앱 업데이트는 새 설치파일을 실행하는 방식입니다. 업무 화면은 서버에서 제공하므로 화면·계산 로직 변경은 서버 배포로 반영됩니다.
