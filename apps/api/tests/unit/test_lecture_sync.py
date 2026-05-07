from datetime import datetime, timedelta, timezone

from bs4 import BeautifulSoup

from apps.api.lecture_sync import (
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
    html = """
    <table><tbody><tr><td>empty</td></tr></tbody></table>
    """

    assert parse_lecture_list(html, "https://www.swmaestro.ai") == []


def test_extract_source_id_supports_known_query_names() -> None:
    assert extract_source_id("https://example.com/view.do?qustnrSn=10268") == "10268"
    assert extract_source_id("https://example.com/view.do?mentoLecSn=77") == "77"
    assert extract_source_id("https://example.com/view.do?id=1") == ""


def test_with_page_index_preserves_existing_query_values() -> None:
    url = "https://example.com/list.do?menuNo=200046&pageIndex=3&searchStatMentolec=A"

    assert _with_page_index(url, 9) == (
        "https://example.com/list.do?menuNo=200046&pageIndex=9&searchStatMentolec=A"
    )


def test_with_page_index_adds_query_when_missing() -> None:
    assert _with_page_index("https://example.com/list.do", 2) == "https://example.com/list.do?pageIndex=2"


def test_content_hash_and_embedding_update_detection() -> None:
    first_hash = make_content_hash("title", "description")
    same_hash = make_content_hash("title", "description")
    changed_hash = make_content_hash("title", "changed")

    assert first_hash == same_hash
    assert first_hash != changed_hash
    assert not needs_embedding_update(first_hash, same_hash)
    assert needs_embedding_update(first_hash, changed_hash)


def test_format_pgvector_returns_pgvector_literal() -> None:
    assert _format_pgvector([0.1, -2.5, 3.0]) == "[0.1,-2.5,3.0]"


def test_clean_text_normalizes_spaces_and_nbsp() -> None:
    assert _clean_text("  hello\xa0\n world\t ") == "hello world"


def test_extract_login_payload_keeps_only_hidden_inputs() -> None:
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
    try:
        _validate_lecture_detail_fields("10268", "", "description")
    except RuntimeError as error:
        assert "title was empty" in str(error)
        assert "10268" in str(error)
    else:
        raise AssertionError("Expected RuntimeError")


def test_validate_lecture_detail_fields_rejects_empty_description() -> None:
    try:
        _validate_lecture_detail_fields("10268", "title", "")
    except RuntimeError as error:
        assert "description was empty" in str(error)
        assert "10268" in str(error)
    else:
        raise AssertionError("Expected RuntimeError")


def test_should_skip_detail_refresh_when_seen_recently() -> None:
    record = LectureRecord(
        source_id="10268",
        title="title",
        description="description",
        status="active",
        content_hash="hash",
        last_seen_at=datetime.now(timezone.utc) - timedelta(seconds=30),
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
