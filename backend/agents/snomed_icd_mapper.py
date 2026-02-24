"""
agents/snomed_icd_mapper.py — Node 4: SNOMED → ICD Direct Mapping

Queries the snomed_icd_map crosswalk table for all ICD codes mapped
to the resolved SNOMED code. Fetches full ICD metadata for each hit.

Output:
  state["candidate_icd_codes"]  — list of ICD candidates with scores
  state["direct_mapped_icd"]    — primary ICD code from direct mapping
  state["mapping_path"]         — "direct" | "no_mapping" | "no_snomed"

If no direct mapping found → mapping_path = "no_mapping"
Node 5 (embedding fallback) will handle that case in Phase 4 Step 5.
"""
from agents.graph import CodingState
from agents.node_runner import safe_node
from database import select, select_one
from logger import get_logger

log = get_logger(__name__)


@safe_node("snomed_icd_map")
async def snomed_icd_mapping_node(state: CodingState) -> CodingState:
    """
    LangGraph Node 4 — SNOMED → ICD Direct Mapping.
    Input:  state["resolved_snomed_code"]
    Output: state["candidate_icd_codes"], state["mapping_path"], state["direct_mapped_icd"]
    """
    session_id = str(state.get("session_id", ""))
    resolved_code = state.get("resolved_snomed_code")

    # ── Guard: no SNOMED code resolved ─────────────────────────────────────
    if not resolved_code:
        log.warning(
            "snomed_map_skipped",
            session_id=session_id,
            reason="no resolved_snomed_code in state",
        )
        state["mapping_path"] = "no_snomed"
        state["candidate_icd_codes"] = []
        state["direct_mapped_icd"] = None
        return state

    # ── Query crosswalk table ───────────────────────────────────────────────
    crosswalk_rows = await select(
        table="snomed_icd_map",
        query="icd_code,mapping_type,confidence,is_primary,notes",
        filters={
            "snomed_code": f"eq.{resolved_code}",
            "order":       "confidence.desc",
        },
    )

    if not crosswalk_rows:
        log.warning(
            "snomed_map_no_results",
            session_id=session_id,
            snomed_code=resolved_code,
        )
        state["mapping_path"] = "no_mapping"
        state["candidate_icd_codes"] = []
        state["direct_mapped_icd"] = None
        return state

    # ── Fetch full ICD details for each mapping ─────────────────────────────
    candidates = []
    for row in crosswalk_rows:
        icd_row = await select_one(
            table="icd_codes",
            query="code,description,is_billable,is_cc,is_mcc,base_reimbursement,version",
            filters={
                "code":        f"eq.{row['icd_code']}",
                "is_billable": "eq.true",          # Only billable codes go forward
            },
        )
        if not icd_row:
            continue  # Skip non-billable or missing codes

        candidates.append({
            "code":           icd_row["code"],
            "description":    icd_row["description"],
            "is_billable":    icd_row["is_billable"],
            "is_cc":          icd_row["is_cc"],
            "is_mcc":         icd_row["is_mcc"],
            "base_reimbursement": float(icd_row["base_reimbursement"]),
            "icd_version":    icd_row.get("version", "ICD-10-CM-2024"),
            # Mapping metadata
            "mapping_type":   row["mapping_type"],
            "confidence":     float(row["confidence"]),
            "is_primary":     row.get("is_primary", False),
            "source":         "snomed_map",
        })

    if not candidates:
        log.warning(
            "snomed_map_all_non_billable",
            session_id=session_id,
            snomed_code=resolved_code,
            crosswalk_hits=len(crosswalk_rows),
        )
        state["mapping_path"] = "no_mapping"
        state["candidate_icd_codes"] = []
        state["direct_mapped_icd"] = None
        return state

    # ── Identify primary mapping ────────────────────────────────────────────
    primary = next((c for c in candidates if c["is_primary"]), candidates[0])

    state["candidate_icd_codes"] = candidates
    state["mapping_path"]        = "direct"
    state["direct_mapped_icd"]   = primary["code"]

    log.info(
        "snomed_mapped",
        session_id=session_id,
        snomed_code=resolved_code,
        mappings_found=len(candidates),
        primary_icd=primary["code"],
        mapping_path="direct",
    )

    return state
