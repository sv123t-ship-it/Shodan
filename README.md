# Shodan IP 대역 Excel 내보내기

GUI 없이 Windows CMD 또는 터미널에서 실행하는 Python 3.10+ 프로그램입니다.
Shodan에 이미 수집된 IP·포트별 정보를 조회하며, 대상에 직접 스캔을 보내지 않습니다.

## 설치 및 실행 (Windows CMD)

```bat
cd Shodan
py -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
set SHODAN_API_KEY=본인의_API_키
python shodan_export.py 203.0.113.0/24 -o report.xlsx
```

예시 대역은 문서용입니다. 조회 권한이 있는 실제 대역으로 바꾸세요.
단일 IP와 IPv6 CIDR도 입력할 수 있습니다. 호스트 비트가 있는 CIDR은 대역 주소로 정규화합니다.
Linux/macOS에서는 `python3 -m venv .venv`, `source .venv/bin/activate`,
`export SHODAN_API_KEY='본인의_API_키'`를 사용하세요.

```bat
python shodan_export.py 203.0.113.0/24 --max-pages 10 -o report_all.xlsx
python shodan_export.py --help
python -m unittest discover -s tests -v
```

`--api-key` 옵션도 지원하지만 명령 기록에 남을 수 있어 환경 변수를 권장합니다.
API 키를 소스나 Git에 저장하지 마세요.

## 출력과 조회 범위

- `Services`: IP, 포트, 프로토콜, 조직, ISP, ASN, 국가·도시, 호스트명,
  도메인, 제품·버전, OS, 마지막 관측 시각, CVE 정보, 배너. 한 행은 하나의 서비스입니다.
- `Summary`: 조회 대역, 전체 서비스 결과 수, 저장한 서비스 수, 고유 IP 수, 완전성 여부.
- Shodan 미수집 IP는 출력되지 않습니다. 모든 IP의 현재 상태나 취약점 유무를 보장하지 않습니다.
- 기본값은 최대 1페이지입니다. 페이지당 최대 100개 서비스를 조회합니다.
  `--max-pages`를 늘리면 추가 조회 권한과 query credit이 필요할 수 있습니다.
  `net:` 검색 사용 가능 여부와 비용은 Shodan 계정 요금제에 따릅니다.
- 조회 중 데이터가 변할 수 있습니다. 일부 결과만 저장된 경우 경고와 Summary를 확인하세요.
- 기존 파일은 덮어쓰지 않습니다. Excel에서 파일을 닫고 새 출력 경로를 사용하세요.
- 셀은 텍스트로 저장하여 배너 등의 수식 실행을 방지합니다.
  Excel 제한으로 셀 텍스트는 32,767자까지 저장됩니다.

인증/권한 오류가 나면 API 키 및 Shodan 요금제·크레딧을 확인하세요.
연결 오류가 나면 `api.shodan.io` HTTPS 접근 및 프록시 설정을 확인하세요.
실제 API 검증에는 유효한 키가 필요하며, 자동 테스트는 가짜 응답으로 동작합니다.
