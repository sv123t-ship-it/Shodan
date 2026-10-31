"""Export Shodan's indexed services for an IP network to Excel."""

import argparse
import ipaddress
import json
import os
from pathlib import Path
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE


class ShodanError(Exception):
    pass


def search(api_key, network, page):
    url = 'https://api.shodan.io/shodan/host/search?' + urlencode(
        {'key': api_key, 'query': f'net:{network}', 'page': page}
    )
    for attempt in range(4):
        try:
            with urlopen(url, timeout=60) as response:
                return json.load(response)
        except HTTPError as exc:
            if (exc.code == 429 or exc.code >= 500) and attempt < 3:
                time.sleep(2 ** (attempt + 1))
                continue
            messages = {
                401: 'API 키가 유효하지 않습니다.',
                403: '조회 권한 또는 query credit이 부족합니다. Shodan 요금제를 확인하세요.',
                429: 'API 요청 한도를 초과했습니다. 잠시 후 다시 실행하세요.',
            }
            raise ShodanError(messages.get(exc.code, f'Shodan HTTP 오류: {exc.code}')) from None
        except (URLError, TimeoutError):
            raise ShodanError('Shodan 연결에 실패했습니다. 네트워크 설정을 확인하세요.') from None
        except (ValueError, UnicodeError):
            raise ShodanError('Shodan 응답을 해석할 수 없습니다.') from None


def collect(api_key, network, max_pages, fetch=search, progress=None):
    rows = []
    total = 0
    for page in range(1, max_pages + 1):
        result = fetch(api_key, network, page)
        if not isinstance(result, dict) or 'error' in result:
            raise ShodanError('Shodan이 조회를 거부했습니다. API 키와 조회 권한을 확인하세요.')
        matches = result.get('matches')
        total = result.get('total')
        if not isinstance(matches, list) or not isinstance(total, int) or total < 0:
            raise ShodanError('Shodan 응답 형식이 올바르지 않습니다.')
        for match in matches:
            try:
                if ipaddress.ip_address(match['ip_str']) not in ipaddress.ip_network(network):
                    raise ValueError()
            except (KeyError, TypeError, ValueError):
                raise ShodanError('조회 대역과 일치하지 않는 IP 응답입니다.') from None
        rows.extend(matches)
        message = f'{page} 페이지: {len(rows)} / {total}개 서비스'
        if progress is None:
            print(message, file=sys.stderr)
        else:
            progress(message)
        if not matches or len(rows) >= total:
            break
        if page < max_pages:
            time.sleep(1)
    return rows, total


def safe(value):
    if value is None:
        return ''
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False)
    return ILLEGAL_CHARACTERS_RE.sub('', str(value))[:32767]


def export(rows, total, network, output):
    workbook = Workbook()
    services = workbook.active
    services.title = 'Services'
    services.append(['IP', 'Port', 'Transport', 'Organization', 'ISP', 'ASN',
                     'Country', 'City', 'Hostnames', 'Domains', 'Product',
                     'Version', 'OS', 'Last seen', 'Vulnerabilities', 'Banner'])
    for item in rows:
        location = item.get('location') or {}
        values = [item.get('ip_str'), item.get('port'), item.get('transport'),
                  item.get('org'), item.get('isp'), item.get('asn'),
                  location.get('country_name'), location.get('city'),
                  item.get('hostnames'), item.get('domains'), item.get('product'),
                  item.get('version'), item.get('os'), item.get('timestamp'),
                  item.get('vulns'), item.get('data')]
        services.append([safe(value) for value in values])
        # Force API-controlled values to text, including strings starting with '='.
        for cell in services[services.max_row]:
            cell.data_type = 's'
    services.freeze_panes = 'A2'
    services.auto_filter.ref = services.dimensions
    for column in services.columns:
        services.column_dimensions[column[0].column_letter].width = 22
    info = workbook.create_sheet('Summary')
    for row in [('Network', network), ('Shodan service results', total),
                ('Exported services', len(rows)),
                ('Unique IPs', len({item['ip_str'] for item in rows})),
                ('Complete', 'Yes' if len(rows) >= total else 'No (page limit or changing results)'),
                ('Note', 'Indexed Shodan results only; missing IPs are not scanned. CVEs are observations, not confirmed vulnerabilities.')]:
        info.append(row)
    info.column_dimensions['A'].width = 28
    info.column_dimensions['B'].width = 100
    # Exclusive creation prevents accidental replacement of an existing report.
    with Path(output).open('xb') as target:
        workbook.save(target)


def positive(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError('1 이상의 값을 입력하세요.')
    return number


def main():
    parser = argparse.ArgumentParser(description='IP 대역의 Shodan 정보를 Excel로 저장합니다.')
    parser.add_argument('network', help='예: 203.0.113.0/24 또는 단일 IP')
    parser.add_argument('-o', '--output', default='shodan_report.xlsx')
    parser.add_argument('--api-key', help='기본값: SHODAN_API_KEY 환경 변수 (권장)')
    parser.add_argument('--max-pages', type=positive, default=1,
                        help='최대 조회 페이지 수 (기본 1, 페이지당 최대 100개 서비스)')
    args = parser.parse_args()
    try:
        network = str(ipaddress.ip_network(args.network, strict=False))
    except ValueError:
        parser.error('유효한 IP 또는 CIDR 대역을 입력하세요.')
    key = args.api_key or os.environ.get('SHODAN_API_KEY')
    if not key:
        parser.error('SHODAN_API_KEY 환경 변수 또는 --api-key가 필요합니다.')
    if Path(args.output).exists():
        parser.error('출력 파일이 이미 존재합니다. 다른 파일명을 지정하세요.')
    try:
        rows, total = collect(key, network, args.max_pages)
        export(rows, total, network, args.output)
    except (ShodanError, OSError) as exc:
        print(f'오류: {exc}', file=sys.stderr)
        return 1
    print(f'저장 완료: {args.output} ({len(rows)}개 서비스, {len({r["ip_str"] for r in rows})}개 IP)')
    if len(rows) < total:
        print('일부 결과만 저장했습니다. 전체 조회가 필요하면 --max-pages를 늘리세요.', file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
