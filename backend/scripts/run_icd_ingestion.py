#!/usr/bin/env python3
"""
Run full ICD-10-CM ingestion pipeline.
"""
import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.icd_ingestion_service import run_full_ingestion, run_index_only_ingestion, validate_counts


def _paths() -> tuple[str, str, str]:
    base = Path(__file__).resolve().parents[2] / "ICD-data"
    icd_txt = base / "icd10orderfiles" / "icd10cm_order_2026.txt"
    tabular_xml = base / "table-and-index" / "Table and Index" / "icd10cm_tabular_2026.xml"
    index_xml = base / "table-and-index" / "Table and Index" / "icd10cm_index_2026.xml"
    return str(icd_txt), str(tabular_xml), str(index_xml)


def _ensure_paths_exist(paths: list[str]) -> None:
    for file_path in paths:
        if not Path(file_path).exists():
            raise FileNotFoundError(f"Missing required file: {file_path}")


async def main() -> None:
    icd_txt, tabular_xml, index_xml = _paths()
    index_only = "--index-only" in sys.argv
    if index_only:
        _ensure_paths_exist([index_xml])
        summary = await run_index_only_ingestion(index_xml, batch_size=500)
    else:
        _ensure_paths_exist([icd_txt, tabular_xml, index_xml])
        summary = await run_full_ingestion(icd_txt, tabular_xml, index_xml, batch_size=500)

    validation = await validate_counts()

    print("\n✅ ICD-10-CM ingestion complete")
    if not index_only:
        print(f"   icd_codes inserted: {summary['icd_codes_inserted']}")
        print(f"   hierarchy inserted: {summary['hierarchy_inserted']}")
        print(f"   metadata inserted: {summary['metadata_inserted']}")
    print(f"   index terms inserted: {summary['index_terms_inserted']}")

    print("\n=== VALIDATION ===")
    print(f"icd_codes: {validation['icd_codes']}")
    print(f"hierarchy: {validation['hierarchy']}")
    print(f"metadata: {validation['metadata']}")
    print(f"index_terms: {validation['index_terms']}")

    total_processed = (
        summary.get("icd_codes_processed", 0)
        + summary.get("hierarchy_processed", 0)
        + summary.get("metadata_processed", 0)
        + summary.get("index_terms_processed", 0)
    )
    total_skipped = (
        summary.get("icd_codes_skipped", 0)
        + summary.get("hierarchy_skipped", 0)
        + summary.get("metadata_skipped", 0)
        + summary.get("index_terms_skipped", 0)
    )

    print("\n=== FINAL REPORT ===")
    print(f"total time (s): {summary['duration_seconds']}")
    print(f"total rows processed: {total_processed}")
    print(f"total rows skipped: {total_skipped}")
    print(f"validation counts: {validation}")


if __name__ == "__main__":
    asyncio.run(main())
