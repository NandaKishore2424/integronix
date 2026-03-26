"""
This agent is responsible for finding official, direct mappings between
the SNOMED CT code (identified in the previous step) and the corresponding
ICD-10-CM code. It queries our internal crosswalk table to find these
pre-established links. This is the preferred, most reliable path.
"""
from agents.graph import CodingState
from agents.node_runner import safe_node
from database import select, select_one
from logger import get_logger

log = get_logger(__name__)


@safe_node("snomed_icd_map")
async def snomed_icd_mapping_node(state: CodingState) -> CodingState:
    # This is the fourth node in our graph. It tries to find a direct
    # mapping from the SNOMED code we found to an ICD-10 code.
    session_id = str(state.get("session_id", ""))

    # ── Fast-path: skip if candidates already populated ─────────────────────
    # WHO ICD API (Node 3) sets candidate_icd_codes directly. Check that key
    # (declared in CodingState, always preserved by LangGraph) rather than
    # who_icd_candidates which is an undeclared key and may be stripped.
    if state.get("candidate_icd_codes"):
        log.info(
            "snomed_icd_map_skipped",
            session_id=session_id,
            reason="candidates_already_populated",
            candidate_count=len(state["candidate_icd_codes"]),
        )
        return state

    resolved_code = state.get("resolved_snomed_code")

    # If we don't have a SNOMED code from the previous step, we can't proceed.
    if not resolved_code:
        log.warning(
            "snomed_map_skipped",
            session_id=session_id,
            reason="no resolved_snomed_code in state",
        )
        # IMPORTANT: do NOT clear candidate_icd_codes — it may contain WHO API results
        # that the early-exit check above missed (defensive guard)
        if not state.get("candidate_icd_codes"):
            state["mapping_path"] = "no_snomed"
            state["candidate_icd_codes"] = []
            state["direct_mapped_icd"] = None
        return state

    # We query our 'snomed_icd_map' table, which contains pre-calculated
    # relationships between SNOMED and ICD-10 codes.
    crosswalk_rows = await select(
        table="snomed_icd_map",
        query="icd_code_id,mapping_type,confidence,is_primary,notes",
        filters={
            "snomed_code": f"eq.{resolved_code}",
            "order":       "confidence.desc",
        },
    )

    # If the query returns nothing, it means there's no direct mapping available.
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

    # For each mapping we found, we fetch the full details of the ICD code.
    candidates = []
    for row in crosswalk_rows:
        icd_row = await select_one(
            table="icd_codes",
            query="code,description,is_billable,is_cc,is_mcc,base_reimbursement,version",
            filters={
                "code":        f"eq.{row['icd_code_id']}",
                "is_billable": "eq.true", # We only care about codes that can actually be used for billing.
            },
        )
        if not icd_row:
            continue  # Skip any non-billable codes.

        # We build a list of candidate codes with all their relevant details.
        candidates.append({
            "code":           icd_row["code"],
            "description":    icd_row["description"],
            "is_billable":    icd_row["is_billable"],
            "is_cc":          icd_row["is_cc"],
            "is_mcc":         icd_row["is_mcc"],
            "base_reimbursement": float(icd_row["base_reimbursement"]),
            "icd_version":    icd_row.get("version", "ICD-10-CM-2024"),
            "mapping_type":   row["mapping_type"],
            "confidence":     float(row["confidence"]),
            "is_primary":     row.get("is_primary", False),
            "source":         "snomed_map",
        })

    # If, after filtering, we have no valid candidates, we're back to the "no_mapping" state.
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
