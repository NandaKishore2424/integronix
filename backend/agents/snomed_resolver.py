"""
agents/snomed_resolver.py — Node 3: SNOMED Concept Resolver (Deterministic + Embedding fallback)

Verifies LLM-suggested SNOMED code against DB.
Falls back to embedding similarity search if code not found.
"""
from agents.graph import CodingState
from database import select_one, select


async def snomed_resolver_node(state: CodingState) -> CodingState:
    """
    LangGraph Node 3 — SNOMED Concept Resolution.
    Input:  state["structured_entities"]["diagnoses"][0]["snomed_candidate"]
    Output: state["resolved_snomed_code"], state["resolved_snomed_desc"], state["snomed_resolution_method"]
    """
    entities = state.get("structured_entities", {})
    diagnoses = entities.get("diagnoses", [])

    if not diagnoses:
        state["resolved_snomed_code"] = None
        state["snomed_resolution_method"] = "not_found"
        return state

    candidate = diagnoses[0].get("snomed_candidate", {})
    suggested_code = candidate.get("code")

    if suggested_code:
        row = await select_one(
            table="snomed_concepts",
            query="snomed_code,description",
            filters={"snomed_code": f"eq.{suggested_code}", "is_active": "eq.true"},
        )
        if row:
            state["resolved_snomed_code"] = row["snomed_code"]
            state["resolved_snomed_desc"] = row["description"]
            state["snomed_resolution_method"] = "llm_suggested"
            return state

    # Fallback: text search on SNOMED concepts (embedding search added in Phase 4)
    diagnosis_text = diagnoses[0].get("text", "")
    keyword = diagnosis_text.split()[0] if diagnosis_text else ""

    rows = await select(
        table="snomed_concepts",
        query="snomed_code,description",
        filters={
            "description": f"ilike.*{keyword}*",
            "is_active": "eq.true",
            "limit": "1",
        },
    )

    if rows:
        state["resolved_snomed_code"] = rows[0]["snomed_code"]
        state["resolved_snomed_desc"] = rows[0]["description"]
        state["snomed_resolution_method"] = "text_matched"
    else:
        state["resolved_snomed_code"] = None
        state["snomed_resolution_method"] = "not_found"

    return state
