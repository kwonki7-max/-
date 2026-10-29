# 회사 공통 서버 배포

직원용 프로그램은 이 서버에 로그인하고 같은 견적조건을 조회·수정합니다. 서버는 회사 계정으로 운영해야 하며 현재 실제 서비스는 개설하지 않았습니다. 아래는 Linux VPS + Docker Compose + Caddy HTTPS 구성입니다. 공급자/요금제를 구매하는 명령은 포함하지 않습니다.

## 사전 준비

- 항상 켜져 있는 Linux 서버, Docker Engine 및 Compose
- 서버 공인 IP로 연결한 도메인 A/AAAA 레코드
- 서버 방화벽 TCP 80/443 허용. 앱의 8000 포트를 인터넷에 열지 않습니다.
- 영구 디스크와 외부 백업 위치

소규모 팀용 단일 서버 구성이며 서버 크기와 비용은 가입할 공급자에서 확인합니다. SQLite를 사용하므로 여러 서버로 수평 확장하기 전 DB 이전이 필요합니다.

## 실행

저장소를 서버에 배치하고:

```bash
cp deploy/.env.example deploy/.env
# deploy/.env의 COMPANY_DOMAIN, ACME_EMAIL을 실제 값으로 수정
# 비밀번호나 API 키는 이 파일에 필요하지 않습니다.
docker compose --env-file deploy/.env -f deploy/compose.yaml up -d --build
docker compose --env-file deploy/.env -f deploy/compose.yaml ps
```

Caddy가 인증서를 발급하고 갱신합니다. 공인 DNS와 80/443 접근이 준비되어야 실제 발급이 됩니다. `/health`가 HTTPS로 200 및 `{"status":"ok"}`를 반환하는지 확인합니다. 앱 컨테이너는 비관리자 UID 10001로 실행되며 `company_data` 볼륨에 DB와 세션키를 보관합니다. `COOKIE_SECURE=1`을 유지하세요.

관리자 계정은 서버의 비공개 터미널에서 생성합니다:

```bash
docker compose --env-file deploy/.env -f deploy/compose.yaml exec app flask --app wsgi create-admin
```

본인 이메일·이름·비밀번호를 입력합니다. 비밀번호를 채팅이나 소스에 넣지 않습니다. 그 후 직원용 설치본에서 로그인해 회원 승인/중지를 관리합니다. 본인 이메일을 일반 회원가입에 먼저 사용하지 마세요.

## 백업 / 갱신

- SQLite의 `backup()` API로 일관된 DB 사본을 생성하고 별도 저장소에 암호화 보관합니다. 실행 중 DB 파일만 단독 복사하면 WAL의 최신 내용이 빠질 수 있습니다.
- `company_data` 내 `session.key`도 안전하게 보관합니다. 계정·백업 파일을 Git에 넣지 않습니다.
- `docker compose ... up -d --build`는 영구 볼륨을 유지합니다. 운영 중 `down -v`를 실행하면 회사 자료가 삭제되므로 사용하지 않습니다.
- 서버 방화벽, 운영체제 패치, 정기 백업·복구 확인, 관리자 계정 관리가 필요합니다.
- 이메일 인증·비밀번호 찾기·자동 앱 업데이트는 초기 버전에 포함되지 않습니다.

## 현재 확인한 범위

Docker 이미지 빌드와 격리된 임시 컨테이너에서 시작·관리자 로그인·조건 조회/수정·재시작 후 데이터 보존을 검증하는 스크립트는 `tests/container_smoke.py`입니다. 실제 DNS·공인 HTTPS 인증서·외부 직원 접속은 서버가 마련된 후 별도로 검증해야 합니다.

관리형 클라우드 개발 환경에서 이미지 빌드 시에는 프록시 CA를 빌드 secret으로 주입합니다. 일반 서버에는 이 세션 전용 인증서를 복사하지 않습니다.
