"""SOMA HTML과 URL에서 lecture sync에 필요한 값을 추출하는 순수 helper."""

from hashlib import sha256
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

from lecture_sync.models import LectureListItem


def parse_lecture_list(html: str, base_url: str) -> list[LectureListItem]:
    """목록 HTML에서 특강 식별자, 제목, 상세 URL, 상태 정보를 추출한다."""

    soup = BeautifulSoup(html, "html.parser")
    table = None
    for candidate in soup.select("table"):
        # 페이지에 여러 table이 있을 수 있으므로 상세 링크가 들어 있는 table만 목록으로 본다.
        if candidate.select_one("a[href*='mentoLec/view.do'], a[href*='qustnrSn=']"):
            table = candidate.select_one("tbody")
            break
    if table is None:
        return []

    lectures: list[LectureListItem] = []
    for row in table.select("tr"):
        cols = row.find_all("td", recursive=False)
        if len(cols) < 7:
            continue

        title_anchor = row.select_one("td.tit a")
        if title_anchor is None:
            title_anchor = row.select_one("a[href*='mentoLec/view.do'], a[href*='qustnrSn=']")
        if title_anchor is None:
            continue

        href = title_anchor.get("href", "")
        detail_url = urljoin(base_url, href if isinstance(href, str) else "")
        # DB unique 기준이 되는 source_id가 없는 row는 동기화 대상에서 제외한다.
        source_id = extract_source_id(detail_url)
        if not source_id:
            continue

        lectures.append(
            LectureListItem(
                source_id=source_id,
                title=_clean_text(title_anchor.get_text(" ", strip=True)),
                detail_url=detail_url,
                receipt_period=(
                    _clean_text(cols[2].get_text(" ", strip=True)) if len(cols) > 2 else None
                ),
                event_date=(
                    _clean_text(cols[3].get_text(" ", strip=True)) if len(cols) > 3 else None
                ),
                status=_clean_text(cols[6].get_text(" ", strip=True)) if len(cols) > 6 else None,
                author=_clean_text(cols[7].get_text(" ", strip=True)) if len(cols) > 7 else None,
                registered_at=(
                    _clean_text(cols[8].get_text(" ", strip=True)) if len(cols) > 8 else None
                ),
            )
        )

    return lectures


def build_embedding_text(title: str, description: str) -> str:
    """임베딩에 사용할 텍스트를 제목과 설명만으로 구성한다."""

    # 메타데이터가 추천 의미를 흐리지 않도록 제목과 설명만 임베딩 입력으로 사용한다.
    return f"{_clean_text(title)}\n{_clean_text(description)}"


def make_content_hash(title: str, description: str) -> str:
    """제목과 설명 변경 여부를 판단하기 위한 SHA-256 해시를 만든다."""

    return sha256(build_embedding_text(title, description).encode("utf-8")).hexdigest()


def needs_embedding_update(existing_hash: str | None, new_hash: str) -> bool:
    """기존 content hash와 새 hash를 비교해 재임베딩 필요 여부를 판단한다."""

    return existing_hash != new_hash


def extract_source_id(detail_url: str) -> str:
    """상세 URL query/path에서 소마 특강 식별자를 추출한다."""

    parsed = urlparse(detail_url)
    query = parse_qs(parsed.query)
    # 현재 SOMA 페이지와 과거/대체 링크 형식을 모두 지원한다.
    for key in ("qustnrSn", "mentoLecSn"):
        values = query.get(key)
        if values and values[0]:
            return values[0]

    return ""


def _with_page_index(url: str, page_index: int) -> str:
    """목록 URL의 pageIndex query 값을 원하는 페이지 번호로 교체한다."""

    parsed = urlparse(url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    # 필터 query는 그대로 두고 pageIndex만 교체해 페이지네이션을 순회한다.
    query["pageIndex"] = [str(page_index)]
    return urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            urlencode(query, doseq=True),
            parsed.fragment,
        )
    )


def _clean_text(value: str) -> str:
    """HTML에서 추출한 텍스트의 공백과 NBSP를 정규화한다."""

    return " ".join(value.replace("\xa0", " ").split())
