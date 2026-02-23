from fastapi import APIRouter
from database import get_db_pool

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check():
    try:
        db = await get_db_pool()
        icd_count = await db.fetchval("SELECT COUNT(*) FROM icd_codes")
        snomed_count = await db.fetchval("SELECT COUNT(*) FROM snomed_concepts")
        return {
            "status": "running",
            "database": "connected",
            "icd_codes_loaded": icd_count,
            "snomed_concepts_loaded": snomed_count,
        }
    except Exception as e:
        return {
            "status": "running",
            "database": "error",
            "detail": str(e),
        }
