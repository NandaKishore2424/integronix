"""
Organization settings lookup for routing logic.
"""
from __future__ import annotations

from database import select_one


async def get_org_settings(org_id: str) -> dict | None:
    if not org_id:
        return None
    return await select_one(
        table="org_settings",
        query="icd_version,claim_scheme,coding_mode",
        filters={"organization_id": f"eq.{org_id}"},
    )
