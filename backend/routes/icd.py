from fastapi import APIRouter, HTTPException, Query, Depends
from services.icd_service import get_icd_by_code, get_snomed_mappings
from services.icd_provider import get_icd_results

from auth import Principal, get_principal

router = APIRouter(prefix="/icd", tags=["ICD"])


@router.get(
    "/snomed/{snomed_code}/mappings",
    summary="Get all ICD-10 codes mapped to a given SNOMED code",
)
async def fetch_snomed_icd_mappings(
    snomed_code: str,
    principal: Principal = Depends(get_principal),
):
    results = await get_snomed_mappings(snomed_code)
    if not results:
        raise HTTPException(
            status_code=404,
            detail=f"No ICD-10 mappings found for SNOMED code '{snomed_code}'",
        )
    return {"snomed_code": snomed_code, "mappings": results}


@router.get(
    "/search",
    summary="Search ICD codes with routing (ICD-10 or ICD-11)",
)
async def search_icd(
    q: str = Query(..., description="Search query"),
    org_id: str = Query(..., description="Organization ID"),
    limit: int = Query(10, ge=1, le=10, description="Max results"),
    principal: Principal = Depends(get_principal),
):
    org_id = principal.assert_org(org_id)
    results = await get_icd_results(q, org_id, limit=limit)
    return {"query": q, "org_id": org_id, "results": results}


# Declared last on purpose: a single-segment path parameter would otherwise
# shadow the literal routes above. FastAPI matches in registration order, so
# with this first, GET /icd/search resolved as code="search" and 404'd.
@router.get("/{code}", summary="Fetch a single ICD-10 code by its code string")
async def fetch_icd_code(
    code: str,
    principal: Principal = Depends(get_principal),
):
    result = await get_icd_by_code(code.upper())
    if not result:
        raise HTTPException(status_code=404, detail=f"ICD code '{code}' not found")
    return result
