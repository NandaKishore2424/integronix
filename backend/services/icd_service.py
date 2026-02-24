from database import select, select_one


async def get_icd_by_code(code: str) -> dict | None:
    rows = await select(
        table="icd_codes",
        query="code,description,chapter,category,is_billable,is_cc,is_mcc,base_reimbursement",
        filters={"code": f"eq.{code}"},
    )
    return rows[0] if rows else None


async def get_snomed_mappings(snomed_code: str) -> list[dict]:
    # Supabase REST doesn't support JOIN directly — fetch in two steps
    map_rows = await select(
        table="snomed_icd_map",
        query="icd_code,mapping_type,confidence,is_primary",
        filters={"snomed_code": f"eq.{snomed_code}", "order": "confidence.desc"},
    )
    if not map_rows:
        return []

    results = []
    for row in map_rows:
        icd = await get_icd_by_code(row["icd_code"])
        if icd and icd.get("is_billable"):
            results.append({**row, **icd})
    return results


async def search_icd_by_text(query_text: str, limit: int = 5) -> list[dict]:
    rows = await select(
        table="icd_codes",
        query="code,description,is_cc,is_mcc,base_reimbursement",
        filters={
            "is_billable": "eq.true",
            "description": f"ilike.*{query_text}*",
            "limit": limit,
        },
    )
    return [{**r, "similarity_score": 0.5, "source": "text_search"} for r in rows]
