"""
ICD-10-CM ingestion orchestration.
"""
from __future__ import annotations

from datetime import datetime
import time

from database import select_count

from logger import get_logger
from services.icd_parsers import parse_icd_txt, parse_tabular_xml, parse_index_xml
from services.icd_loader_service import (
    dataclass_rows_to_dicts,
    bulk_insert_icd_codes,
    bulk_insert_hierarchy,
    bulk_insert_metadata,
    bulk_insert_index_terms,
    compute_leaf_and_parent_codes,
    update_icd_billable_flags,
)

log = get_logger(__name__)


def _now_iso() -> str:
    return datetime.utcnow().isoformat()


async def run_full_ingestion(
    icd_txt_path: str,
    tabular_xml_path: str,
    index_xml_path: str,
    batch_size: int = 500,
) -> dict:
    """
    Run full ingestion pipeline.
    NOTE: PostgREST does not support true multi-step transactions.
    Each phase is executed sequentially with logging.
    """
    start_time = time.perf_counter()
    summary: dict = {
        "started_at": _now_iso(),
        "icd_codes_inserted": 0,
        "hierarchy_inserted": 0,
        "metadata_inserted": 0,
        "index_terms_inserted": 0,
        "icd_codes_processed": 0,
        "hierarchy_processed": 0,
        "metadata_processed": 0,
        "index_terms_processed": 0,
        "icd_codes_skipped": 0,
        "hierarchy_skipped": 0,
        "metadata_skipped": 0,
        "index_terms_skipped": 0,
    }

    log.info("icd_ingestion_start", started_at=summary["started_at"])

    # Phase 1: ICD codes (from TXT)
    log.info("phase_start", phase="icd_codes")
    try:
        icd_rows = parse_icd_txt(icd_txt_path)
        icd_payload = dataclass_rows_to_dicts(icd_rows)
        summary["icd_codes_processed"] = len(icd_payload)
        summary["icd_codes_inserted"] = await bulk_insert_icd_codes(icd_payload, batch_size=batch_size)
        summary["icd_codes_skipped"] = summary["icd_codes_processed"] - summary["icd_codes_inserted"]
        log.info("phase_complete", phase="icd_codes", rows=summary["icd_codes_inserted"])
    except Exception as exc:
        log.error("phase_failed", phase="icd_codes", error=str(exc))
        raise

    # Phase 2: Tabular XML (hierarchy)
    log.info("phase_start", phase="hierarchy")
    try:
        hierarchy_rows, metadata_rows = parse_tabular_xml(tabular_xml_path)
        hierarchy_payload = dataclass_rows_to_dicts(hierarchy_rows)
        metadata_payload = dataclass_rows_to_dicts(metadata_rows)

        summary["hierarchy_processed"] = len(hierarchy_payload)
        summary["hierarchy_inserted"] = await bulk_insert_hierarchy(hierarchy_payload, batch_size=batch_size)
        summary["hierarchy_skipped"] = summary["hierarchy_processed"] - summary["hierarchy_inserted"]
        log.info("phase_complete", phase="hierarchy", rows=summary["hierarchy_inserted"])
    except Exception as exc:
        log.error("phase_failed", phase="hierarchy", error=str(exc))
        raise

    # Phase 2b: Tabular XML (metadata)
    log.info("phase_start", phase="metadata")
    try:
        summary["metadata_processed"] = len(metadata_payload)
        summary["metadata_inserted"] = await bulk_insert_metadata(metadata_payload, batch_size=batch_size)
        summary["metadata_skipped"] = summary["metadata_processed"] - summary["metadata_inserted"]
        log.info("phase_complete", phase="metadata", rows=summary["metadata_inserted"])
    except Exception as exc:
        log.error("phase_failed", phase="metadata", error=str(exc))
        raise

    # Phase 2c: mark billable flags using hierarchy leaf detection
    leaf_codes, parent_codes = compute_leaf_and_parent_codes(hierarchy_payload)
    await update_icd_billable_flags(leaf_codes, parent_codes, batch_size=batch_size)

    # Phase 3: Index XML (search terms)
    log.info("phase_start", phase="index")
    try:
        index_rows, invalid_index_codes = parse_index_xml(index_xml_path)
        index_payload = dataclass_rows_to_dicts(index_rows)
        summary["index_terms_processed"] = len(index_payload)
        summary["index_terms_inserted"] = await bulk_insert_index_terms(index_payload, batch_size=batch_size)
        summary["index_terms_skipped"] = summary["index_terms_processed"] - summary["index_terms_inserted"]
        summary["index_terms_invalid_codes"] = invalid_index_codes
        log.info("index_invalid_codes_filtered", count=invalid_index_codes)
        log.info("phase_complete", phase="index", rows=summary["index_terms_inserted"])
    except Exception as exc:
        log.error("phase_failed", phase="index", error=str(exc))
        raise

    summary["completed_at"] = _now_iso()
    summary["duration_seconds"] = round(time.perf_counter() - start_time, 2)
    log.info("icd_ingestion_complete", **summary)

    return summary


async def run_index_only_ingestion(index_xml_path: str, batch_size: int = 500) -> dict:
    start_time = time.perf_counter()
    summary: dict = {
        "started_at": _now_iso(),
        "index_terms_inserted": 0,
        "index_terms_processed": 0,
        "index_terms_skipped": 0,
        "index_terms_invalid_codes": 0,
    }

    log.info("icd_index_ingestion_start", started_at=summary["started_at"])
    log.info("phase_start", phase="index")
    try:
        index_rows, invalid_index_codes = parse_index_xml(index_xml_path)
        index_payload = dataclass_rows_to_dicts(index_rows)
        summary["index_terms_processed"] = len(index_payload)
        summary["index_terms_inserted"] = await bulk_insert_index_terms(index_payload, batch_size=batch_size)
        summary["index_terms_skipped"] = summary["index_terms_processed"] - summary["index_terms_inserted"]
        summary["index_terms_invalid_codes"] = invalid_index_codes
        log.info("index_invalid_codes_filtered", count=invalid_index_codes)
        log.info("phase_complete", phase="index", rows=summary["index_terms_inserted"])
    except Exception as exc:
        log.error("phase_failed", phase="index", error=str(exc))
        raise

    summary["completed_at"] = _now_iso()
    summary["duration_seconds"] = round(time.perf_counter() - start_time, 2)
    log.info("icd_index_ingestion_complete", **summary)
    return summary


async def validate_counts() -> dict:
    return {
        "icd_codes": await select_count("icd_codes"),
        "hierarchy": await select_count("icd_code_hierarchy"),
        "metadata": await select_count("icd_code_metadata"),
        "index_terms": await select_count("icd_index_terms"),
    }
