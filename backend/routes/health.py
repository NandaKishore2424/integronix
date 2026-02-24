from fastapi import APIRouter
from database import select

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check():
    try:
        rows = await select("icd_codes", query="code", filters={"limit": "1"})
        icd_count_rows = await select("icd_codes", query="count", filters={})
        snomed_count_rows = await select("snomed_concepts", query="count", filters={})
        return {
            "status": "running",
            "database": "connected",
            "icd_codes_sample": rows[0]["code"] if rows else None,
        }
    except Exception as e:
        return {
            "status": "running",
            "database": "error",
            "detail": str(e),
        }
