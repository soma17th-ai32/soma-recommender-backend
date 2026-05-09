from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
async def ready() -> dict[str, object]:
    return {
        "status": "ready",
        "dependencies": {
            "ttl_storage": "ok",
            "vectordb": "stub",
            "llm": "stub",
            "embedding": "stub",
        },
    }
