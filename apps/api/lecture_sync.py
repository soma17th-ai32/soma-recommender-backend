from __future__ import annotations

import os
import time
from dataclasses import dataclass
from hashlib import sha256
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv


@dataclass(frozen=True)
class LectureListItem:
    """목록 페이지에서 확인한 접수 가능 특강의 최소 정보."""

    source_id: str
    title: str
    detail_url: str
    status: str | None = None
    receipt_period: str | None = None
    event_date: str | None = None
    author: str | None = None
    registered_at: str | None = None


@dataclass(frozen=True)
class LectureDetail:
    """상세 페이지에서 수집한 임베딩/저장 대상 특강 정보."""

    source_id: str
    title: str
    description: str
    detail_url: str
    content_hash: str


@dataclass(frozen=True)
class LectureRecord:
    """DB에 이미 저장되어 있다고 가정하는 기존 특강 row 정보."""

    source_id: str
    title: str
    description: str
    status: str
    content_hash: str


@dataclass(frozen=True)
class SyncLectureResult:
    """한 번의 특강 동기화 작업 결과 요약."""

    fetched_count: int
    inserted_count: int
    updated_count: int
    activated_count: int
    inactivated_count: int
    embedding_pending_count: int


@dataclass(frozen=True)
class SomaSettings:
    """소마 사이트 크롤링에 필요한 환경변수 기반 설정."""

    base_url: str
    login_url: str
    lecture_list_url: str
    username: str
    password: str
    timeout_seconds: float = 20.0
    user_agent: str = "Mozilla/5.0 (compatible; SOMA-Recommender/0.1)"
    max_pages: int | None = None


def sync_lecture() -> SyncLectureResult:
    """소마 특강 목록 수집부터 DB 상태 갱신까지 수행하는 메인 진입점."""

    # 1. 프로젝트 루트 .env와 환경변수에서 소마 접속 설정을 읽는다.
    settings = load_soma_settings()

    # 2. 같은 로그인 쿠키를 유지할 HTTP session을 만든다.
    session = create_soma_session(settings)

    # 3. 현재 session으로 특강 목록에 접근할 수 없으면 로그인한다.
    if not is_session_alive(session, settings):
        login_soma_site(session, settings)

    # 4. 접수 가능 상태의 특강 목록을 모든 페이지에서 수집한다.
    available_lectures = fetch_available_lecture_list(session, settings)

    # 5. 수집 결과를 기준으로 신규/수정/비활성화/재활성화 대상을 처리한다.
    return refresh_lecture_status(available_lectures, session, settings)


def print_live_lecture_preview(limit: int = 10) -> None:
    """로컬 확인용으로 실제 요청을 보내 목록 상위 N개와 첫 상세 내용을 출력한다."""

    settings = load_soma_settings()
    session = create_soma_session(settings)

    if not is_session_alive(session, settings):
        login_soma_site(session, settings)

    lectures = fetch_available_lecture_list(session, settings)

    print(f"\n=== SOMA lecture list top {limit} ===")
    for index, lecture in enumerate(lectures[:limit], start=1):
        print(
            f"{index}. "
            f"source_id={lecture.source_id}, "
            f"title={lecture.title}, "
            f"status={lecture.status}, "
            f"author={lecture.author}, "
            f"registered_at={lecture.registered_at}, "
            f"detail_url={lecture.detail_url}"
        )

    if not lectures:
        print("\nNo available lectures found.")
        return

    detail = fetch_lecture_detail(session, lectures[0].detail_url, settings)

    print("\n=== SOMA first lecture detail ===")
    print(f"source_id={detail.source_id}")
    print(f"title={detail.title}")
    print(f"detail_url={detail.detail_url}")
    print(f"content_hash={detail.content_hash}")
    print("description:")
    print(detail.description)


def load_soma_settings() -> SomaSettings:
    """프로젝트 루트 .env와 환경변수에서 소마 사이트 접속 설정을 읽는다."""

    load_dotenv()

    max_pages = os.getenv("SWM_MAX_PAGES")
    timeout_seconds = os.getenv("SWM_TIMEOUT_SECONDS", "20")

    required_values = {
        "SWM_BASE_URL": os.getenv("SWM_BASE_URL"),
        "SWM_LOGIN_URL": os.getenv("SWM_LOGIN_URL"),
        "SWM_NOTICE_LIST_URL": os.getenv("SWM_NOTICE_LIST_URL"),
        "SWM_USERNAME": os.getenv("SWM_USERNAME"),
        "SWM_PASSWORD": os.getenv("SWM_PASSWORD"),
    }
    missing = [name for name, value in required_values.items() if not value]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

    return SomaSettings(
        base_url=required_values["SWM_BASE_URL"] or "",
        login_url=required_values["SWM_LOGIN_URL"] or "",
        lecture_list_url=required_values["SWM_NOTICE_LIST_URL"] or "",
        username=required_values["SWM_USERNAME"] or "",
        password=required_values["SWM_PASSWORD"] or "",
        timeout_seconds=float(timeout_seconds),
        user_agent=os.getenv("USER_AGENT", "Mozilla/5.0 (compatible; SOMA-Recommender/0.1)"),
        max_pages=int(max_pages) if max_pages else None,
    )


def create_soma_session(settings: SomaSettings) -> requests.Session:
    """로그인 쿠키를 유지할 requests 세션을 생성하고 기본 헤더를 설정한다."""

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": settings.user_agent,
            "Referer": settings.login_url,
        }
    )
    return session


def login_soma_site(session: requests.Session, settings: SomaSettings) -> None:
    """소마 로그인 페이지의 고정 form 구조를 사용해 로그인한다."""

    response = session.get(settings.login_url, timeout=settings.timeout_seconds)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    form = soup.select_one("form#login_form")
    if form is None:
        raise RuntimeError("SOMA login form was not found.")

    payload = _extract_login_payload(form)
    payload["username"] = settings.username
    payload["password"] = settings.password

    _check_login_available(session, settings, payload)

    action_raw = form.get("action")
    action = action_raw if isinstance(action_raw, str) else ""
    if not action:
        raise RuntimeError("SOMA login form action was not found.")
    action_url = urljoin(settings.base_url, action)
    login_response = session.post(action_url, data=payload, timeout=settings.timeout_seconds)
    login_response.raise_for_status()
    login_response = _submit_auto_forms(session, login_response, settings)

    if _looks_like_login_page(login_response.text, str(login_response.url)):
        raise RuntimeError("SOMA login appears to have failed.")

    time.sleep(1.0)


def is_session_alive(session: requests.Session, settings: SomaSettings) -> bool:
    """현재 세션으로 특강 목록 페이지에 접근 가능한지 확인한다."""

    response = session.get(
        _with_page_index(settings.lecture_list_url, 1),
        timeout=settings.timeout_seconds,
    )
    response.raise_for_status()
    return not _response_requires_login(response)


def fetch_available_lecture_list(
    session: requests.Session,
    settings: SomaSettings,
) -> list[LectureListItem]:
    """접수 가능 특강 목록 페이지를 순회하며 목록 정보를 수집한다."""

    lectures: list[LectureListItem] = []
    page_index = 1

    while True:
        if settings.max_pages is not None and page_index > settings.max_pages:
            break

        response = session.get(
            _with_page_index(settings.lecture_list_url, page_index),
            timeout=settings.timeout_seconds,
        )
        response.raise_for_status()

        if _response_requires_login(response):
            login_soma_site(session, settings)
            response = session.get(
                _with_page_index(settings.lecture_list_url, page_index),
                timeout=settings.timeout_seconds,
            )
            response.raise_for_status()

        page_items = parse_lecture_list(response.text, settings.base_url)
        if not page_items:
            break

        lectures.extend(page_items)
        page_index += 1
        time.sleep(0.5)

    deduped = {lecture.source_id: lecture for lecture in lectures}
    return list(deduped.values())


def fetch_lecture_detail(
    session: requests.Session,
    detail_url: str,
    settings: SomaSettings,
) -> LectureDetail:
    """상세 페이지 링크에 접속해 제목과 설명을 수집한다."""

    response = session.get(detail_url, timeout=settings.timeout_seconds)
    response.raise_for_status()

    if _response_requires_login(response):
        login_soma_site(session, settings)
        response = session.get(detail_url, timeout=settings.timeout_seconds)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    source_id = _extract_detail_source_id(soup) or extract_source_id(detail_url)
    title = _extract_detail_title(soup)
    description = _extract_detail_description(soup)
    return LectureDetail(
        source_id=source_id,
        title=title,
        description=description,
        detail_url=detail_url,
        content_hash=make_content_hash(title, description),
    )


def refresh_lecture_status(
    available_lectures: list[LectureListItem],
    session: requests.Session,
    settings: SomaSettings,
) -> SyncLectureResult:
    """수집된 접수 가능 목록을 기준으로 DB 상태와 임베딩 갱신 대상을 계산한다."""

    existing_records = get_existing_lectures()
    existing_by_id = {lecture.source_id: lecture for lecture in existing_records}
    available_ids = {lecture.source_id for lecture in available_lectures}
    existing_ids = set(existing_by_id)

    inserted_count = 0
    updated_count = 0
    activated_count = 0
    embedding_pending_count = 0

    missing_ids = existing_ids - available_ids
    inactivated_count = mark_lectures_inactive(missing_ids)

    for lecture in available_lectures:
        existing = existing_by_id.get(lecture.source_id)
        if existing is not None and existing.status == "inactive":
            mark_lecture_active(lecture.source_id)
            activated_count += 1

        if existing is None:
            detail = fetch_lecture_detail(session, lecture.detail_url, settings)
            insert_lecture(detail)
            embedding_pending_count += queue_embedding_update(detail)
            inserted_count += 1
            continue

        detail = fetch_lecture_detail(session, lecture.detail_url, settings)
        if needs_embedding_update(existing.content_hash, detail.content_hash):
            update_lecture(detail)
            embedding_pending_count += queue_embedding_update(detail)
            updated_count += 1

    return SyncLectureResult(
        fetched_count=len(available_lectures),
        inserted_count=inserted_count,
        updated_count=updated_count,
        activated_count=activated_count,
        inactivated_count=inactivated_count,
        embedding_pending_count=embedding_pending_count,
    )


def parse_lecture_list(html: str, base_url: str) -> list[LectureListItem]:
    """목록 HTML에서 특강 식별자, 제목, 상세 URL, 상태 정보를 추출한다."""

    soup = BeautifulSoup(html, "html.parser")
    table = None
    for candidate in soup.select("table"):
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

        href = title_anchor.get("href")
        detail_url = urljoin(base_url, href if isinstance(href, str) else "")
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

    return f"{_clean_text(title)}\n{_clean_text(description)}"


def make_content_hash(title: str, description: str) -> str:
    """제목과 설명 변경 여부를 판단하기 위한 SHA-256 해시를 만든다."""

    return sha256(build_embedding_text(title, description).encode("utf-8")).hexdigest()


def needs_embedding_update(existing_hash: str | None, new_hash: str) -> bool:
    """기존 content hash와 새 hash를 비교해 재임베딩 필요 여부를 판단한다."""

    return existing_hash != new_hash


def get_existing_lectures() -> list[LectureRecord]:
    """DB에서 기존 특강 목록을 조회한다. 실제 DB 연결 시 구현한다."""

    # TODO: PostgreSQL에서 lectures row를 조회하도록 구현한다.
    raise NotImplementedError("DB connection is not configured yet.")


def insert_lecture(detail: LectureDetail) -> None:
    """신규 특강을 DB에 저장한다. 실제 DB 연결 시 구현한다."""

    # TODO: 신규 특강 row를 lectures 테이블에 insert하도록 구현한다.
    raise NotImplementedError("DB connection is not configured yet.")


def update_lecture(detail: LectureDetail) -> None:
    """내용이 변경된 기존 특강 row를 갱신한다. 실제 DB 연결 시 구현한다."""

    # TODO: title/description/detail_url/content_hash/updated_at을 update하도록 구현한다.
    raise NotImplementedError("DB connection is not configured yet.")


def mark_lectures_inactive(source_ids: set[str]) -> int:
    """이번 목록에 없는 기존 특강을 접수 불가능 상태로 변경한다."""

    if not source_ids:
        return 0
    # TODO: source_id 목록에 해당하는 row의 status를 inactive로 update하도록 구현한다.
    raise NotImplementedError("DB connection is not configured yet.")


def mark_lecture_active(source_id: str) -> None:
    """이전에 비활성화된 특강이 다시 보이면 접수 가능 상태로 복구한다."""

    # TODO: source_id에 해당하는 row의 status를 active로 update하도록 구현한다.
    raise NotImplementedError("DB connection is not configured yet.")


def queue_embedding_update(detail: LectureDetail) -> int:
    """임베딩 생성과 pgvector upsert를 예약/수행한다. 실제 연동 시 구현한다."""

    # TODO: Upstage embedding 생성 후 lectures.embedding과 embedding_updated_at을 갱신한다.
    raise NotImplementedError("Embedding and pgvector upsert are not configured yet.")


def extract_source_id(detail_url: str) -> str:
    """상세 URL query/path에서 소마 특강 식별자를 추출한다."""

    parsed = urlparse(detail_url)
    query = parse_qs(parsed.query)
    for key in ("qustnrSn", "mentoLecSn"):
        values = query.get(key)
        if values and values[0]:
            return values[0]

    return ""


def _extract_detail_title(soup: BeautifulSoup) -> str:
    """상세 HTML의 '모집 명' 라벨에서 특강 제목을 추출한다."""

    return _extract_detail_value(soup, "모집 명")


def _extract_detail_description(soup: BeautifulSoup) -> str:
    """상세 HTML의 본문 영역에서 특강 설명만 추출한다."""

    for selector in (".bbs-view-new > .cont", ".bbs-view-new .cont"):
        candidate = soup.select_one(selector)
        if candidate is not None:
            text = _clean_text(candidate.get_text(" ", strip=True))
            if text:
                return text
    return ""


def _extract_detail_source_id(soup: BeautifulSoup) -> str:
    """상세 form의 hidden input에서 소마 특강 식별자를 추출한다."""

    input_tag = soup.select_one("form#board input[name='qustnrSn']")
    if input_tag is None:
        input_tag = soup.select_one("input[name='qustnrSn']")
    if input_tag is None:
        return ""
    value = input_tag.get("value", "")
    return _clean_text(value if isinstance(value, str) else "")


def _extract_detail_value(soup: BeautifulSoup, label: str) -> str:
    """상세 정보 영역에서 특정 라벨에 대응하는 값을 추출한다."""

    for group in soup.select(".bbs-view-new .group"):
        title = group.select_one("strong.t")
        content = group.select_one(".c")
        if title is None or content is None:
            continue
        if _clean_text(title.get_text(" ", strip=True)) == label:
            return _clean_text(content.get_text(" ", strip=True))
    return ""


def _submit_auto_forms(
    session: requests.Session,
    response: requests.Response,
    settings: SomaSettings,
    max_hops: int = 3,
) -> requests.Response:
    """로그인 후 hidden form 자동 제출이 필요한 경우 연속 제출한다."""

    current = response
    for _ in range(max_hops):
        soup = BeautifulSoup(current.text, "html.parser")
        form = soup.find("form")
        if form is None:
            return current

        action_raw = form.get("action")
        action = action_raw if isinstance(action_raw, str) else ""
        hidden_inputs = form.select("input[type='hidden'][name]")
        if not action or not hidden_inputs:
            return current

        payload: dict[str, str] = {}
        for input_tag in hidden_inputs:
            name = input_tag.get("name")
            if not isinstance(name, str) or not name:
                continue
            value = input_tag.get("value", "")
            payload[name] = value if isinstance(value, str) else ""
        if not payload:
            return current

        current = session.post(
            urljoin(settings.base_url, action),
            data=payload,
            timeout=settings.timeout_seconds,
        )
        current.raise_for_status()

    return current


def _check_login_available(
    session: requests.Session,
    settings: SomaSettings,
    payload: dict[str, str],
) -> None:
    """로그인 페이지 JavaScript와 동일하게 계정 잠금 상태를 먼저 확인한다."""

    response = session.post(
        urljoin(settings.base_url, "/sw/member/user/checkStat.json"),
        data=payload,
        timeout=settings.timeout_seconds,
    )
    response.raise_for_status()
    data = response.json()
    if data.get("resultCode") != "success":
        raise RuntimeError("SOMA login is temporarily unavailable for this account.")


def _extract_login_payload(form) -> dict[str, str]:
    """로그인 form의 hidden input 값을 payload로 보존한다."""

    payload: dict[str, str] = {}
    for input_tag in form.select("input[name]"):
        name_raw = input_tag.get("name", "")
        name = name_raw.strip() if isinstance(name_raw, str) else ""
        if not name:
            continue
        input_type_raw = input_tag.get("type") or "text"
        input_type = input_type_raw.lower() if isinstance(input_type_raw, str) else "text"
        if input_type != "hidden":
            continue
        value = input_tag.get("value", "")
        payload[name] = value if isinstance(value, str) else ""
    return payload


def _response_requires_login(response: requests.Response) -> bool:
    """응답 URL과 HTML 내용을 보고 로그인이 필요한 응답인지 판단한다."""

    response_url = str(response.url).lower()
    if "/sw/main/main.do" in response_url:
        return True
    return _looks_like_login_page(response.text, response_url)


def _looks_like_login_page(html: str, url: str) -> bool:
    """HTML 텍스트와 URL이 로그인 화면처럼 보이는지 판단한다."""

    lowered_url = url.lower()
    if "tologin.do" in lowered_url or "forlogin.do" in lowered_url:
        return True

    soup = BeautifulSoup(html, "html.parser")
    page_text = soup.get_text(" ", strip=True)
    if "로그아웃" in page_text or "MY PAGE" in page_text:
        return False
    return "로그인" in page_text and "비밀번호" in page_text


def _with_page_index(url: str, page_index: int) -> str:
    """목록 URL의 pageIndex query 값을 원하는 페이지 번호로 교체한다."""

    parsed = urlparse(url)
    query = parse_qs(parsed.query, keep_blank_values=True)
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


if __name__ == "__main__":
    print_live_lecture_preview()
