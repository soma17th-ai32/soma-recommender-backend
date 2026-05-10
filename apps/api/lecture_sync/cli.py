import argparse

from lecture_sync.crawler import (
    create_soma_session,
    fetch_available_lecture_list,
    fetch_lecture_detail,
    is_session_alive,
    login_soma_site,
)
from lecture_sync.embedding import embed_lecture_detail
from lecture_sync.service import sync_lecture
from lecture_sync.settings import load_soma_settings, load_upstage_settings


def print_live_lecture_preview(limit: int = 10) -> None:
    """로컬 확인용으로 실제 요청을 보내 목록 상위 N개와 첫 상세 내용을 출력한다."""

    settings = load_soma_settings()
    with create_soma_session(settings) as session:
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


def print_live_embedding_preview(limit: int = 10, preview_size: int = 8) -> None:
    """첫 번째 접수 가능 특강 상세 내용을 Upstage로 임베딩하고 요약 출력한다."""

    settings = load_soma_settings()
    with create_soma_session(settings) as session:
        if not is_session_alive(session, settings):
            login_soma_site(session, settings)

        lectures = fetch_available_lecture_list(session, settings)
        if not lectures:
            print("\nNo available lectures found.")
            return

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

        detail = fetch_lecture_detail(session, lectures[0].detail_url, settings)

    embedding = embed_lecture_detail(detail)

    print("\n=== SOMA first lecture detail ===")
    print(f"source_id={detail.source_id}")
    print(f"title={detail.title}")
    print(f"detail_url={detail.detail_url}")
    print(f"content_hash={detail.content_hash}")
    print("description:")
    print(detail.description)

    print("\n=== SOMA first lecture embedding ===")
    print(f"model={load_upstage_settings().embedding_model}")
    print(f"source_id={detail.source_id}")
    print(f"title={detail.title}")
    print(f"embedding_dimension={len(embedding)}")
    print(f"embedding_preview={embedding[:preview_size]}")


def main() -> None:
    """로컬 확인용 CLI 진입점."""

    parser = argparse.ArgumentParser(description="SOMA lecture crawler utilities")
    parser.add_argument(
        "--embed",
        action="store_true",
        help="also create an Upstage embedding for the first lecture",
    )
    parser.add_argument(
        "--sync",
        action="store_true",
        help="sync available lectures into PostgreSQL",
    )
    args = parser.parse_args()

    if args.sync:
        result = sync_lecture()
        print("\n=== SOMA lecture sync result ===")
        print(f"fetched_count={result.fetched_count}")
        print(f"inserted_count={result.inserted_count}")
        print(f"updated_count={result.updated_count}")
        print(f"activated_count={result.activated_count}")
        print(f"inactivated_count={result.inactivated_count}")
        print(f"embedding_pending_count={result.embedding_pending_count}")
        return

    if args.embed:
        print_live_embedding_preview()
        return

    print_live_lecture_preview()
