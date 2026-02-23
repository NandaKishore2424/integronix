from database import get_db_pool


async def get_icd_by_code(code: str) -> dict | None:
    db = await get_db_pool()
    row = await db.fetchrow(
        """
        SELECT code, description, chapter, category,
               is_billable, is_cc, is_mcc, base_reimbursement
        FROM icd_codes
        WHERE code = $1
        """,
        code,
    )
    return dict(row) if row else None


async def get_snomed_mappings(snomed_code: str) -> list[dict]:
    db = await get_db_pool()
    rows = await db.fetch(
        """
        SELECT
            sim.icd_code,
            sim.mapping_type,
            sim.confidence,
            sim.is_primary,
            ic.description,
            ic.is_cc,
            ic.is_mcc,
            ic.base_reimbursement
        FROM snomed_icd_map sim
        JOIN icd_codes ic ON ic.code = sim.icd_code
        WHERE sim.snomed_code = $1
          AND ic.is_billable = TRUE
        ORDER BY sim.confidence DESC
        """,
        snomed_code,
    )
    return [dict(r) for r in rows]


async def search_icd_by_text(query_text: str, limit: int = 5) -> list[dict]:
    """
    Placeholder: text-based ICD search before embeddings are loaded.
    Uses ILIKE for simple keyword matching.
    """
    db = await get_db_pool()
    rows = await db.fetch(
        """
        SELECT code, description, is_cc, is_mcc, base_reimbursement,
               0.5 AS similarity_score
        FROM icd_codes
        WHERE is_billable = TRUE
          AND description ILIKE $1
        LIMIT $2
        """,
        f"%{query_text}%",
        limit,
    )
    return [dict(r) for r in rows]
