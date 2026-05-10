"""SOMA 사이트에 로그인하고 특강 목록/상세 HTML을 수집하는 crawler."""

import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from lecture_sync.models import LectureData, LectureDetail, LectureListItem, SomaSettings
from lecture_sync.parser import (
    _clean_text,
    _with_page_index,
    extract_source_id,
    make_content_hash,
    parse_lecture_list,
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

    # 먼저 로그인 페이지를 받아 hidden input과 form action을 실제 HTML에서 읽는다.
    response = session.get(settings.login_url, timeout=settings.timeout_seconds)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    form = soup.select_one("form#login_form")
    if form is None:
        raise RuntimeError("SOMA login form was not found.")

    payload = _extract_login_payload(form)
    payload["username"] = settings.username
    payload["password"] = settings.password

    # 로그인 페이지 JavaScript가 호출하는 계정 상태 확인 API를 동일하게 거친다.
    _check_login_available(session, settings, payload)

    action = form.get("action")
    if not isinstance(action, str) or not action:
        raise RuntimeError("SOMA login form action was not found.")
    action_url = urljoin(settings.base_url, action)
    login_response = session.post(action_url, data=payload, timeout=settings.timeout_seconds)
    login_response.raise_for_status()
    # SOMA 로그인은 hidden form 자동 submit을 거칠 수 있어 후속 form도 처리한다.
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
        # 로컬 테스트에서는 SWM_MAX_PAGES로 외부 요청과 embedding 비용을 제한할 수 있다.
        if settings.max_pages is not None and page_index > settings.max_pages:
            break

        response = session.get(
            _with_page_index(settings.lecture_list_url, page_index),
            timeout=settings.timeout_seconds,
        )
        response.raise_for_status()

        # 세션이 만료되면 같은 session에 다시 로그인하고 현재 페이지 요청을 재시도한다.
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
        # SOMA 사이트에 짧은 간격으로 연속 요청하지 않도록 페이지 간 텀을 둔다.
        time.sleep(0.5)

    # 페이지 이동 중 중복 row가 보이더라도 source_id 기준으로 하나만 유지한다.
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

    # 상세 페이지 접근 중 세션이 만료된 경우도 목록 수집과 동일하게 복구한다.
    if _response_requires_login(response):
        login_soma_site(session, settings)
        response = session.get(detail_url, timeout=settings.timeout_seconds)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    source_id = _extract_detail_source_id(soup) or extract_source_id(detail_url)
    title = _extract_detail_title(soup)
    description = _extract_detail_description(soup)
    # 제목이 비어 있으면 강의를 식별하기 어려우므로 저장 전에 차단한다.
    _validate_lecture_detail_fields(source_id, title, description)
    return LectureDetail(
        source_id=source_id,
        title=title,
        description=description,
        detail_url=detail_url,
        content_hash=make_content_hash(title, description),
    )


def _validate_lecture_detail_fields(source_id: str, title: str, description: str) -> None:
    """DB 저장과 임베딩 전에 상세 페이지 필수 필드가 비어 있지 않은지 확인한다."""

    if not title:
        raise RuntimeError(f"SOMA lecture detail title was empty: source_id={source_id}")


def fetch_lecture_data(
    session: requests.Session,
    lecture: LectureListItem,
    settings: SomaSettings,
) -> LectureData:
    """목록 row와 상세 페이지 본문을 합쳐 DB 저장용 데이터를 만든다."""

    detail = fetch_lecture_detail(session, lecture.detail_url, settings)
    # 목록 페이지의 접수 기간/작성자 정보와 상세 페이지의 본문 정보를 하나의 저장 단위로 합친다.
    return LectureData(
        source_id=detail.source_id,
        title=detail.title,
        description=detail.description,
        detail_url=detail.detail_url,
        receipt_period=lecture.receipt_period,
        event_date=lecture.event_date,
        author=lecture.author,
        registered_at=lecture.registered_at,
        content_hash=detail.content_hash,
    )


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
        if not isinstance(action, str) or not action or not hidden_inputs:
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

        # hidden input만 있는 relay form을 순서대로 submit해 최종 로그인 세션을 완성한다.
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
        raw_name = input_tag.get("name", "")
        name = raw_name.strip() if isinstance(raw_name, str) else ""
        if not name:
            continue
        raw_input_type = input_tag.get("type") or "text"
        input_type = raw_input_type.lower() if isinstance(raw_input_type, str) else "text"
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
    # 로그인 후 페이지에는 로그아웃/MY PAGE가 보이므로 로그인 화면으로 오탐하지 않는다.
    if "로그아웃" in page_text or "MY PAGE" in page_text:
        return False
    return "로그인" in page_text and "비밀번호" in page_text
