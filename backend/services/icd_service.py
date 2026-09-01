from database import select, select_one
import re

# Keyword matches covering less than this fraction-derived score are noise.
MIN_KEYWORD_SCORE = 0.45


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


async def search_icd_by_text(query_text: str, limit: int = 10) -> list[dict]:
    query_text = (query_text or "").strip()
    if not query_text:
        return []

    normalized = _normalize_query(query_text)
    tokens = [t for t in normalized.split() if len(t) >= 3]

    index_rows = await _search_index_terms(normalized, tokens)

    # Score index matches by how much of the QUERY the term actually covers.
    # A flat score here once billed pneumonia as "abrasion of lower back":
    # the single token "lower" (from "lower lobe") matched "lower back" and
    # scored the same 0.8 as a genuine match. Coverage scoring makes a
    # one-token-out-of-six match score ~0.13 and fall below the floor.
    query_tokens = set(tokens)
    code_scores: dict[str, float] = {}
    for row in index_rows:
        code = row.get("code")
        term = row.get("normalized_term") or ""
        if not code:
            continue
        if term == normalized:
            score = 1.0
        elif normalized and normalized in term:
            score = 0.9
        elif query_tokens:
            term_tokens = set(term.split())
            matched = len(query_tokens & term_tokens)
            score = 0.8 * (matched / len(query_tokens))
        else:
            score = 0.0
        code_scores[code] = max(code_scores.get(code, 0.0), score)

    # Relevance floor: better to return nothing (and let the caller mark the
    # case for human review) than to return a confident wrong code.
    code_scores = {c: sc for c, sc in code_scores.items() if sc >= MIN_KEYWORD_SCORE}

    if code_scores:
        codes = sorted(set(code_scores.keys()))
        icd_rows = await _fetch_icd_codes_by_codes(codes)
        results = []
        for row in icd_rows:
            code = row.get("code")
            score = code_scores.get(code, 0.8)
            results.append({**row, "score": score})
        return _sort_results(results, limit)

    # Fallback: description search
    desc_rows = await select(
        table="icd_codes",
        query="code,description,is_billable,is_cc,is_mcc,base_reimbursement",
        filters={
            "description": f"ilike.*{query_text}*",
            "limit": limit,
        },
    )
    results = [{**r, "score": 0.5} for r in desc_rows]
    return _sort_results(results, limit)


def _normalize_query(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


async def _search_index_terms(normalized: str, tokens: list[str]) -> list[dict]:
    or_parts = [f"normalized_term.ilike.*{normalized}*"] if normalized else []
    or_parts.extend([f"normalized_term.ilike.*{t}*" for t in tokens])
    if not or_parts:
        return []

    return await select(
        table="icd_index_terms",
        query="term,normalized_term,code",
        filters={
            "or": f"({','.join(or_parts)})",
            "limit": 20,
        },
    )


async def _fetch_icd_codes_by_codes(codes: list[str]) -> list[dict]:
    if not codes:
        return []
    code_list = ",".join(codes)
    return await select(
        table="icd_codes",
        query="code,description,is_billable,is_cc,is_mcc,base_reimbursement",
        filters={"code": f"in.({code_list})"},
    )


def _sort_results(results: list[dict], limit: int) -> list[dict]:
    results.sort(
        key=lambda r: (
            -(float(r.get("score") or 0.0)),
            len((r.get("description") or "")),
        )
    )
    return results[:limit]
