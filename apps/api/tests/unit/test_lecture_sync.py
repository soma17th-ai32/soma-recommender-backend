"""lecture sync의 외부 요청 없는 순수 로직을 고정하는 단위 테스트."""

# ruff: noqa: E501

from datetime import UTC, datetime, timedelta

from bs4 import BeautifulSoup

from lecture_sync import (
    LectureRecord,
    SomaSettings,
    _clean_text,
    _extract_login_payload,
    _format_pgvector,
    _validate_lecture_detail_fields,
    _with_page_index,
    extract_source_id,
    make_content_hash,
    needs_embedding_update,
    parse_lecture_list,
    should_skip_detail_refresh,
)


def test_parse_lecture_list_extracts_rows_with_optional_author_columns() -> None:
    # SOMA 목록 row는 작성자/등록일 컬럼이 있을 수도 없을 수도 있어 두 케이스를 함께 검증한다.
    html = """
    <table>
      <tbody>
        <tr>
          <td>1</td><td class="tit"><a href="/sw/mypage/mentoLec/view.do?qustnrSn=100">첫 특강</a></td>
          <td>2026-05-01 ~ 2026-05-02</td><td>2026-05-03</td><td>10명</td><td>0명</td><td>접수중</td>
        </tr>
        <tr>
          <td>2</td><td class="tit"><a href="/sw/mypage/mentoLec/view.do?qustnrSn=101">둘째 특강</a></td>
          <td>2026-05-04 ~ 2026-05-05</td><td>2026-05-06</td><td>20명</td><td>1명</td><td>접수중</td>
          <td>홍길동</td><td>2026-04-30</td>
        </tr>
      </tbody>
    </table>
    """

    lectures = parse_lecture_list(html, "https://www.swmaestro.ai")

    assert len(lectures) == 2
    assert lectures[0].source_id == "100"
    assert lectures[0].title == "첫 특강"
    assert lectures[0].author is None
    assert lectures[1].source_id == "101"
    assert lectures[1].detail_url == "https://www.swmaestro.ai/sw/mypage/mentoLec/view.do?qustnrSn=101"
    assert lectures[1].receipt_period == "2026-05-04 ~ 2026-05-05"
    assert lectures[1].event_date == "2026-05-06"
    assert lectures[1].status == "접수중"
    assert lectures[1].author == "홍길동"
    assert lectures[1].registered_at == "2026-04-30"


def test_parse_lecture_list_ignores_tables_without_lecture_links() -> None:
    # 상세 링크가 없는 table은 특강 목록 table로 오인하지 않아야 한다.
    html = """
    <table><tbody><tr><td>empty</td></tr></tbody></table>
    """

    assert parse_lecture_list(html, "https://www.swmaestro.ai") == []


def test_extract_source_id_supports_known_query_names() -> None:
    # 현재 URL 파라미터(qustnrSn)와 대체 파라미터(mentoLecSn)를 모두 source_id로 인정한다.
    assert extract_source_id("https://example.com/view.do?qustnrSn=10268") == "10268"
    assert extract_source_id("https://example.com/view.do?mentoLecSn=77") == "77"
    assert extract_source_id("https://example.com/view.do?id=1") == ""


def test_with_page_index_preserves_existing_query_values() -> None:
    # 검색 필터 query는 유지하고 pageIndex만 교체해야 목록 페이지 순회가 깨지지 않는다.
    url = "https://example.com/list.do?menuNo=200046&pageIndex=3&searchStatMentolec=A"

    assert _with_page_index(url, 9) == (
        "https://example.com/list.do?menuNo=200046&pageIndex=9&searchStatMentolec=A"
    )


def test_with_page_index_adds_query_when_missing() -> None:
    # pageIndex가 없는 기본 URL도 첫 페이지 이후 요청에 사용할 수 있어야 한다.
    assert _with_page_index("https://example.com/list.do", 2) == "https://example.com/list.do?pageIndex=2"


def test_content_hash_and_embedding_update_detection() -> None:
    # 제목/설명 조합이 같으면 embedding 재생성을 피하고, 내용이 바뀌면 재생성 대상으로 본다.
    first_hash = make_content_hash("title", "description")
    same_hash = make_content_hash("title", "description")
    changed_hash = make_content_hash("title", "changed")

    assert first_hash == same_hash
    assert first_hash != changed_hash
    assert not needs_embedding_update(first_hash, same_hash)
    assert needs_embedding_update(first_hash, changed_hash)


def test_format_pgvector_returns_pgvector_literal() -> None:
    # repository는 list[float]를 pgvector literal로 cast해서 UPDATE한다.
    assert _format_pgvector([0.1, -2.5, 3.0]) == "[0.1,-2.5,3.0]"


def test_clean_text_normalizes_spaces_and_nbsp() -> None:
    # HTML에서 섞여 들어오는 NBSP, 줄바꿈, 탭은 content_hash 전에 동일한 공백으로 정규화한다.
    assert _clean_text("  hello\xa0\n world\t ") == "hello world"


def test_extract_login_payload_keeps_only_hidden_inputs() -> None:
    # 로그인 payload는 SOMA form의 hidden 값만 보존하고 사용자 입력 필드는 설정값으로 채운다.
    soup = BeautifulSoup(
        """
        <form>
          <input type="hidden" name="csrf" value="token">
          <input name="empty_type" value="visible">
          <input type="text" name="username" value="user">
          <input type="hidden" value="missing-name">
        </form>
        """,
        "html.parser",
    )

    assert _extract_login_payload(soup.select_one("form")) == {"csrf": "token"}


def test_validate_lecture_detail_fields_rejects_empty_title() -> None:
    # 빈 제목은 NOT NULL 제약을 통과하는 가비지 row가 될 수 있어 저장 전에 실패시킨다.
    try:
        _validate_lecture_detail_fields("10268", "", "description")
    except RuntimeError as error:
        assert "title was empty" in str(error)
        assert "10268" in str(error)
    else:
        raise AssertionError("Expected RuntimeError")


def test_validate_lecture_detail_fields_rejects_empty_description() -> None:
    # SOMA 실제 데이터에는 본문이 빈 특강도 있으므로 제목만 있으면 sync 대상에 포함한다.
    _validate_lecture_detail_fields("10268", "title", "")


def test_should_skip_detail_refresh_when_seen_recently() -> None:
    # refresh interval 안에 이미 본 기존 row는 상세 페이지와 embedding 호출을 건너뛸 수 있다.
    record = LectureRecord(
        source_id="10268",
        title="title",
        description="description",
        status="active",
        content_hash="hash",
        last_seen_at=datetime.now(UTC) - timedelta(seconds=30),
    )
    settings = SomaSettings(
        base_url="https://example.com",
        login_url="https://example.com/login",
        lecture_list_url="https://example.com/list",
        username="user",
        password="password",
        detail_refresh_interval_seconds=60,
    )

    assert should_skip_detail_refresh(record, settings)


def test_should_not_skip_detail_refresh_without_interval_or_seen_at() -> None:
    # interval 설정이 없거나 last_seen_at이 없으면 정확성을 위해 상세 페이지를 다시 확인한다.
    record = LectureRecord(
        source_id="10268",
        title="title",
        description="description",
        status="active",
        content_hash="hash",
        last_seen_at=None,
    )
    settings = SomaSettings(
        base_url="https://example.com",
        login_url="https://example.com/login",
        lecture_list_url="https://example.com/list",
        username="user",
        password="password",
    )

    assert not should_skip_detail_refresh(record, settings)
