from __future__ import annotations

import gzip
import ipaddress
import importlib
import json
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from curl_cffi import requests as cf_requests
from curl_cffi.requests.exceptions import RequestException

try:
    geoip2_database = importlib.import_module('geoip2.database')
    AddressNotFoundError = importlib.import_module('geoip2.errors').AddressNotFoundError
except ImportError:
    geoip2_database = None

    class AddressNotFoundError(Exception):
        """Fallback exception type used when the optional runtime dependency is absent."""

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

if TYPE_CHECKING:
    from geoip2.database import Reader
    from playwright.sync_api import Browser, Playwright


SOURCES: dict[str, str] = {
    'https://www.wetest.vip/page/cloudfront/address_v4.html': 'WeTest',
    'https://api.uouin.com/cloudflare.html': 'UOUIN',
    'https://bestcf.pages.dev/xinyitang3/ipv4.txt': 'Mia',
    'https://bestcf.pages.dev/tiancheng/all.txt': 'Tiancheng',
    'https://raw.githubusercontent.com/gslege/CloudflareIP/refs/heads/main/SG.txt': 'Gslege-SG',
    'https://bestcf.pages.dev/s5gy/hk.txt': 's5gy-hk',
    'https://bestcf.pages.dev/s5gy/jp.txt': 's5gy-jp',
    'https://raw.githubusercontent.com/gslege/CloudflareIP/refs/heads/main/US.txt': 'Gslege-US',
    'https://raw.githubusercontent.com/ymyuuu/IPDB/refs/heads/main/BestCF/bestcfv4.txt': 'IPDB',
    'https://vps789.com/openApi/cfIpApi': 'VPS789',
    'https://api.4ce.cn/api/bestCFIP': 'vvhan',
    'https://bestcf.pages.dev/luoli/all.txt': 'LuoLi',
}

DEFAULT_PORT: int = 443
HEADERS: dict[str, str] = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0',
}
IPV4_ENDPOINT_PATTERN: str = (
    r'(?<![\w.])((?:[0-9]{1,3}\.){3}[0-9]{1,3})'
    r'(?::([0-9]{1,5}))?(?![\w.:/])'
)
OUTPUT_FILE: Path = Path('best-cf-ipv4.txt')
MMDB_URL: str = 'https://cdn.jsdelivr.net/npm/geolite2-city/GeoLite2-City.mmdb.gz'
MMDB_FILE: Path = Path(__file__).resolve().parent / 'data' / 'GeoLite2-City.mmdb'
MAX_RETRIES: int = 3
RETRY_BACKOFF_FACTOR: float = 2.0


def _session() -> cf_requests.Session:
    """Create a session with Chrome TLS fingerprint impersonation."""
    session = cf_requests.Session(impersonate='chrome')
    session.headers.update(HEADERS)
    return session


def fetch(session: cf_requests.Session, url: str, timeout: int = 15) -> str:
    """Fetch a URL with retry support and return response text."""
    last_err: RequestException | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = session.get(url, timeout=timeout)
            resp.raise_for_status()
            return resp.text
        except RequestException as e:
            last_err = e
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_FACTOR ** attempt)
    assert last_err is not None
    raise last_err


def extract_ipv4(text: str) -> set[tuple[str, str]]:
    """Extract valid IPv4 endpoints, preserving explicitly provided ports."""
    stripped = text.lstrip('\ufeff\t\n\r ')
    if stripped.startswith(('{', '[')):
        try:
            return extract_json_ipv4(json.loads(stripped))
        except json.JSONDecodeError:
            return set()
    if stripped.startswith('<'):
        parser = VisibleTextParser()
        parser.feed(text)
        text = parser.text

    endpoints: set[tuple[str, str]] = set()
    for match in re.finditer(IPV4_ENDPOINT_PATTERN, text):
        try:
            ip = str(ipaddress.ip_address(match.group(1)))
            port_number = int(match.group(2) or DEFAULT_PORT)
            if not 1 <= port_number <= 65535:
                continue
            endpoints.add((ip, str(port_number)))
        except ValueError:
            continue
    return endpoints


def extract_json_ipv4(value: object) -> set[tuple[str, str]]:
    """Extract endpoints only from fields explicitly named 'ip'."""
    if isinstance(value, dict):
        endpoints: set[tuple[str, str]] = set()
        for key, child in value.items():
            if key.casefold() == 'ip' and isinstance(child, str):
                endpoints.update(extract_ipv4(child))
            else:
                endpoints.update(extract_json_ipv4(child))
        return endpoints
    if isinstance(value, list):
        endpoints: set[tuple[str, str]] = set()
        for child in value:
            endpoints.update(extract_json_ipv4(child))
        return endpoints
    return set()


class VisibleTextParser(HTMLParser):
    """Collect visible HTML text while ignoring scripts and styles."""

    def __init__(self) -> None:
        super().__init__()
        self._ignored_depth = 0
        self._parts: list[str] = []

    @property
    def text(self) -> str:
        return ' '.join(self._parts)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() in {'script', 'style'}:
            self._ignored_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() in {'script', 'style'} and self._ignored_depth:
            self._ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._ignored_depth:
            self._parts.append(data)


def sort_endpoints(endpoints: set[tuple[str, str]]) -> list[tuple[str, str]]:
    """Sort endpoints deterministically by IP and numeric port."""
    return sorted(endpoints, key=lambda endpoint: (ipaddress.ip_address(endpoint[0]), int(endpoint[1])))


def country_to_flag(code: str) -> str:
    if len(code) != 2 or code == 'XX':
        return ''
    return chr(ord(code[0]) - 65 + 0x1F1E6) + chr(ord(code[1]) - 65 + 0x1F1E6)


def _ensure_mmdb() -> None:
    """Download the offline GeoLite2 City database if missing."""
    if MMDB_FILE.exists():
        return
    MMDB_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary_file = MMDB_FILE.with_suffix('.tmp')
    last_err: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f'Downloading {MMDB_URL} (attempt {attempt}/{MAX_RETRIES}) ...')
            with _session() as sess:
                resp = sess.get(MMDB_URL, timeout=120)
                resp.raise_for_status()
                temporary_file.write_bytes(gzip.decompress(resp.content))

            if geoip2_database is None:
                raise RuntimeError(
                    'geoip2 not installed; run: pip install -r .github/scripts/requirements.txt'
                )
            validation_reader = geoip2_database.Reader(str(temporary_file))
            validation_reader.close()
            temporary_file.replace(MMDB_FILE)
            return
        except Exception as e:
            last_err = e
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_FACTOR ** attempt)
        finally:
            temporary_file.unlink(missing_ok=True)

    assert last_err is not None
    raise last_err


_reader: Reader | None = None


def _get_reader() -> Reader:
    """Lazily create a singleton GeoLite2 database reader."""
    global _reader
    if geoip2_database is None:
        raise RuntimeError('geoip2 not installed; run: pip install -r .github/scripts/requirements.txt')
    if _reader is None:
        _ensure_mmdb()
        _reader = geoip2_database.Reader(str(MMDB_FILE))
    reader = _reader
    assert reader is not None
    return reader


def close_reader() -> None:
    """Close the singleton database reader, releasing its file handle."""
    global _reader
    if _reader is not None:
        reader, _reader = _reader, None
        reader.close()


def lookup_country(ip: str) -> str:
    """Look up an ISO-3166 country code via GeoLite2, returning 'XX' on failure."""
    try:
        response = _get_reader().city(ip)
        code = response.country.iso_code
        if code is not None and re.fullmatch(r'[A-Z]{2}', code):
            return code
        code = response.registered_country.iso_code
        if code is not None and re.fullmatch(r'[A-Z]{2}', code):
            return code
    except AddressNotFoundError:
        pass
    return 'XX'


def beijing_timestamp() -> str:
    """Return current Beijing time as YYYY-MM-DD HH:MM string."""
    return (datetime.now(timezone.utc) + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M')


_browser: Browser | None = None
_pw: Playwright | None = None


def _get_browser() -> 'Browser':
    """Lazily start a reusable headless Chromium instance."""
    global _browser, _pw
    if sync_playwright is None:
        raise RuntimeError('playwright not installed; run: pip install playwright && playwright install chromium')
    if _browser is None:
        pw = sync_playwright().start()
        try:
            browser = pw.chromium.launch(headless=True)
        except Exception:
            pw.stop()
            raise
        _pw = pw
        _browser = browser
    return _browser


def fetch_rendered(url: str, timeout: int = 30000) -> str:
    """Render a JS page with headless Chromium and return the final HTML."""
    context = _get_browser().new_context(user_agent=HEADERS['User-Agent'])
    try:
        page = context.new_page()
        page.goto(url, wait_until='networkidle', timeout=timeout)
        return page.content()
    finally:
        context.close()


def close_browser() -> None:
    """Close the reusable browser and Playwright runtime if they were started."""
    global _browser, _pw
    browser, _browser = _browser, None
    playwright, _pw = _pw, None
    errors: list[Exception] = []
    if browser is not None:
        try:
            browser.close()
        except Exception as e:
            errors.append(e)
    if playwright is not None:
        try:
            playwright.stop()
        except Exception as e:
            errors.append(e)
    if errors:
        raise errors[0]


def _cleanup_resources(session: cf_requests.Session, active_exception: bool) -> None:
    """Attempt every cleanup action without replacing an active main exception."""
    errors: list[Exception] = []
    actions: tuple[Callable[[], Any], ...] = (session.close, close_browser, close_reader)
    for action in actions:
        try:
            action()
        except Exception as e:
            errors.append(e)
    if errors and not active_exception:
        raise errors[0]


def collect_ips(session: cf_requests.Session) -> set[tuple[str, str]]:
    """Collect IPv4 endpoints, degrading from HTTP to headless browser.

    A source is considered fetched successfully only when it yields at least
    one valid IPv4 address; otherwise the next fetcher tier is tried.
    """
    all_ips: set[tuple[str, str]] = set()
    tiers = [
        ('HTTP', lambda u: fetch(session, u)),
        ('Browser', fetch_rendered),
    ]
    for url, name in SOURCES.items():
        for label, fetcher in tiers:
            try:
                ips = extract_ipv4(fetcher(url))
            except Exception as e:
                print(f'  [{name}] {label} failed: {e}')
                continue
            if ips:
                all_ips.update(ips)
                print(f'  [{name}] {label}: {len(ips)} IPv4')
                break
            print(f'  [{name}] {label}: 0 IPv4, trying next tier')
        else:
            print(f'  [{name}] all fetchers failed')
    return all_ips


def enrich_locations(ips: set[tuple[str, str]]) -> dict[str, str]:
    """Query geographic locations for all IPv4 endpoints via the offline database."""
    _get_reader()
    entries: dict[str, str] = {}
    for ip, port in ips:
        entries[f'{ip}:{port}'] = lookup_country(ip)
    return entries


def main() -> int:
    """Collect Cloudflare IPs, query locations, and write result file."""
    print('Collecting Cloudflare IPs...\n')

    session = _session()
    try:
        all_ips = collect_ips(session)
        if not all_ips:
            print('No IPs collected, skip')
            return 1
        print(f'\n{len(all_ips)} unique IPv4')

        print('Querying locations...')
        entries = enrich_locations(all_ips)

        tmp = OUTPUT_FILE.with_suffix('.tmp')
        timestamp = beijing_timestamp()
        with tmp.open('w', encoding='utf-8') as f:
            f.write(f'#{len(entries)} bestips updated at {timestamp}\n')
            for ip, port in sort_endpoints(all_ips):
                ip_port = f'{ip}:{port}'
                f.write(f'{ip_port}#{entries[ip_port]} {country_to_flag(entries[ip_port])}\n')
        tmp.replace(OUTPUT_FILE)
        print(f'\n{len(entries)} IPs written to {OUTPUT_FILE}')
        return 0
    finally:
        _cleanup_resources(session, sys.exception() is not None)


if __name__ == '__main__':
    sys.exit(main())
