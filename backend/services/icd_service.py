from database import select, select_one
from logger import get_logger
import re

log = get_logger(__name__)

# Keyword matches covering less than this fraction-derived score are noise.
MIN_KEYWORD_SCORE = 0.45

# Row caps for the three search passes. Every query is ORDERED so the same
# note always gets the same candidates. An unordered LIMIT returned whatever
# rows Postgres happened to scan first — the E11.331 retinopathy code reached
# a chronic-kidney-disease note that way, and a rerun could return a different
# set (E11.01 appeared in one run and not in another).
_INDEX_ALL_TOKENS_LIMIT = 50
_INDEX_ANY_TOKEN_LIMIT = 20
_DESCRIPTION_LIMIT = 200

# Joining words. Dropped from search tokens so "diabetes and CKD" does not
# demand an index term that literally contains "and".
_SEARCH_STOPWORDS = frozenset({"and", "the", "for", "has", "had", "was", "are", "also", "but"})

# Coding boilerplate. It says nothing about the patient, so it never makes a
# row a better or worse match for what the clinician wrote.
_PRECISION_IGNORED = frozenset({
    "with", "without", "and", "the", "for", "due", "from", "not", "nos", "nec",
    "other", "unspecified", "specified", "elsewhere", "classified", "type", "stage",
})

# "type 2" and "stage 3b" are single clinical facts. Split into words, the
# number was dropped as too short, so "type 2 diabetes" also matched every
# TYPE 1 index entry and "stage 3" could not tell 3a from 3b.
_TOKEN_RE = re.compile(r"\b(?:type|stage)\s+(?:\d+[ab]?|iii[ab]?|ii|iv|v|i)\b|[a-z0-9]+")
_ROMAN = {"i": "1", "ii": "2", "iii": "3", "iv": "4", "v": "5"}


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
    tokens = query_tokens(normalized)

    # Pass 1: index terms containing EVERY token. The index is organised as
    # "diabetes ... type 2 with chronic kidney disease", so requiring all the
    # tokens lands on the entry the clinician's wording points at. The old
    # any-token query matched "type" inside "phenotype" and returned twenty
    # unrelated rows, none of which cleared the floor.
    match_mode = "all_tokens"
    code_scores, code_precision = {}, {}
    if tokens:
        rows = await _search_index_terms_all(tokens)
        code_scores, code_precision = _score_index_rows(rows, normalized, tokens)

    # Pass 2: the original any-token query, kept for partial matches — a
    # query whose words never all appear in one index entry can still cover
    # enough of them to clear the floor.
    if not code_scores:
        match_mode = "any_token"
        rows = await _search_index_terms(normalized, tokens)
        code_scores, code_precision = _score_index_rows(rows, normalized, tokens)

    if code_scores:
        codes = sorted(set(code_scores.keys()))
        icd_rows = await _fetch_icd_codes_by_codes(codes)
        results = []
        for row in icd_rows:
            code = row.get("code")
            score = code_scores.get(code, 0.8)
            results.append({**row, "score": score})
        results = _sort_results(results, limit, tiebreak=code_precision)
        log.info("icd_text_search", match_mode=match_mode, tokens=len(tokens), results=len(results))
        return results

    # Pass 3: code descriptions. This used to return whatever five rows
    # contained the raw phrase, each at a flat 0.5 — which is how
    # "Type 2 diabetes mellitus" produced a retinopathy-with-macular-edema
    # code. Now a description must cover the query AND be mostly made of the
    # query's words: a long description full of findings the clinician never
    # wrote scores low and is dropped.
    desc_terms = tokens or ([normalized] if normalized else [])
    desc_rows = await _search_descriptions(desc_terms)
    results = []
    desc_precision: dict[str, float] = {}
    for row in desc_rows:
        text = _normalize_query(row.get("description") or "")
        score, precision = _coverage_score(normalized, tokens, text)
        score = round(score * precision, 4)
        if score >= MIN_KEYWORD_SCORE and row.get("code"):
            results.append({**row, "score": score})
            desc_precision[row["code"]] = precision
    results = _sort_results(results, limit, tiebreak=desc_precision)
    log.info("icd_text_search", match_mode="description", tokens=len(tokens), results=len(results))
    return results


def query_tokens(normalized: str) -> list[str]:
    """
    Search tokens for an already-normalised string, in order, without repeats.

    "type 2" and "stage 3b" stay whole (Roman numerals become digits, so
    "stage iii" reads as "stage 3"). Other words need three letters and must
    not be a joining word.
    """
    out: list[str] = []
    for match in _TOKEN_RE.finditer(normalized or ""):
        token = match.group(0)
        if " " in token:
            word, value = token.split()
            token = f"{word} {_roman_to_digit(value)}"
        elif len(token) < 3 or token in _SEARCH_STOPWORDS:
            continue
        if token not in out:
            out.append(token)
    return out


def _roman_to_digit(value: str) -> str:
    if value in _ROMAN:
        return _ROMAN[value]
    if value[-1:] in {"a", "b"} and value[:-1] in _ROMAN:
        return _ROMAN[value[:-1]] + value[-1]
    return value


def _has_phrase(phrase: str, text: str) -> bool:
    return re.search(rf"\b{re.escape(phrase)}\b", text) is not None


def _token_in(token: str, text: str, words: set[str]) -> bool:
    return _has_phrase(token, text) if " " in token else token in words


def _coverage_score(normalized: str, tokens: list[str], text: str) -> tuple[float, float]:
    """
    (score, precision) for one normalised index term or description.

    score — how much of the QUERY the text covers. A flat score here once
    billed pneumonia as "abrasion of lower back": the single token "lower"
    (from "lower lobe") matched "lower back" and scored the same 0.8 as a
    genuine match. Coverage scoring makes a one-token-out-of-six match score
    ~0.13 and fall below the floor.

    precision — how much of the TEXT is the query's clinical words. It ranks
    "diabetes type 2" above "diabetes type 2 with cataract" when both cover
    the query in full.
    """
    words = set(text.split())
    matched = [t for t in tokens if _token_in(t, text, words)]
    if text == normalized:
        score = 1.0
    elif normalized and _has_phrase(normalized, text):
        score = 0.9   # the whole query, as words ("stage 3" is not in "stage 3a")
    elif tokens:
        score = 0.8 * (len(matched) / len(tokens))
    else:
        score = 0.0

    text_clinical = [t for t in query_tokens(text) if t not in _PRECISION_IGNORED]
    if not text_clinical:
        return score, 1.0
    matched_clinical = sum(1 for t in matched if t not in _PRECISION_IGNORED)
    return score, min(1.0, matched_clinical / len(text_clinical))


def _score_index_rows(
    rows: list[dict], normalized: str, tokens: list[str],
) -> tuple[dict[str, float], dict[str, float]]:
    """Best score and precision per code, with the relevance floor applied."""
    code_scores: dict[str, float] = {}
    code_precision: dict[str, float] = {}
    for row in rows:
        code = row.get("code")
        if not code:
            continue
        score, precision = _coverage_score(normalized, tokens, row.get("normalized_term") or "")
        if score > code_scores.get(code, -1.0) or (
            score == code_scores.get(code) and precision > code_precision.get(code, 0.0)
        ):
            code_scores[code] = score
            code_precision[code] = precision

    # Relevance floor: better to return nothing (and let the caller mark the
    # case for human review) than to return a confident wrong code.
    kept = {c: sc for c, sc in code_scores.items() if sc >= MIN_KEYWORD_SCORE}
    return kept, {c: code_precision[c] for c in kept}


def _normalize_query(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


async def _search_index_terms_all(tokens: list[str]) -> list[dict]:
    """Index terms containing every token (a PostgREST `and` of ilikes)."""
    if not tokens:
        return []
    and_parts = [f"normalized_term.ilike.*{t}*" for t in tokens]
    return await select(
        table="icd_index_terms",
        query="term,normalized_term,code",
        filters={
            "and": f"({','.join(and_parts)})",
            "order": "normalized_term.asc",
            "limit": _INDEX_ALL_TOKENS_LIMIT,
        },
    )


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
            "order": "normalized_term.asc",
            "limit": _INDEX_ANY_TOKEN_LIMIT,
        },
    )


async def _search_descriptions(terms: list[str]) -> list[dict]:
    """Code descriptions containing every term, in code order."""
    if not terms:
        return []
    and_parts = [f"description.ilike.*{t}*" for t in terms]
    return await select(
        table="icd_codes",
        query="code,description,is_billable,is_cc,is_mcc,base_reimbursement",
        filters={
            "and": f"({','.join(and_parts)})",
            "order": "code.asc",
            "limit": _DESCRIPTION_LIMIT,
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


def _sort_results(
    results: list[dict], limit: int, tiebreak: dict[str, float] | None = None,
) -> list[dict]:
    tiebreak = tiebreak or {}
    results.sort(
        key=lambda r: (
            -(float(r.get("score") or 0.0)),
            -tiebreak.get(r.get("code"), 0.0),
            len((r.get("description") or "")),
            r.get("code") or "",
        )
    )
    return results[:limit]
