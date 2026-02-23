from fastapi import APIRouter, HTTPException
from services.icd_service import get_icd_by_code, get_snomed_mappings

router = APIRouter(prefix="/icd", tags=["ICD"])


@router.get("/{code}", summary="Fetch a single ICD-10 code by its code string")
async def fetch_icd_code(code: str):
    result = await get_icd_by_code(code.upper())
    if not result:
        raise HTTPException(status_code=404, detail=f"ICD code '{code}' not found")
    return result


@router.get(
    "/snomed/{snomed_code}/mappings",
    summary="Get all ICD-10 codes mapped to a given SNOMED code",
)
async def fetch_snomed_icd_mappings(snomed_code: str):
    results = await get_snomed_mappings(snomed_code)
    if not results:
        raise HTTPException(
            status_code=404,
            detail=f"No ICD-10 mappings found for SNOMED code '{snomed_code}'",
        )
    return {"snomed_code": snomed_code, "mappings": results}
