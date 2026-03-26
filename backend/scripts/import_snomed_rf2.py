#!/usr/bin/env python3
"""
Import SNOMED CT RF2 snapshot files into Supabase/PostgreSQL.

This script performs a 3-pass ingestion:
1) Concepts      -> snomed_concepts
2) Descriptions  -> snomed_descriptions + FSN update on snomed_concepts
3) Relationships -> snomed_relationships

Environment variables:
- DATABASE_URL: postgresql://... direct DB connection string
- SNOMED_RF2_DIR: directory containing Snapshot/Terminology files
"""
from __future__ import annotations

import csv
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Iterable

csv.field_size_limit(sys.maxsize)

from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import execute_values, execute_batch

BATCH_SIZE = 50_000
FSN_TYPE_ID = "900000000000003001"


def extract_semantic_tag(fsn: str) -> str:
    match = re.search(r"\(([^)]+)\)$", fsn.strip())
    return f"({match.group(1)})" if match else ""


def parse_effective_date(raw: str) -> datetime.date:
    return datetime.strptime(raw, "%Y%m%d").date()


def iter_tsv_rows(path: Path) -> Iterable[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for row in reader:
            yield row


def flush_concepts(cursor, rows: list[tuple]) -> int:
    if not rows:
        return 0
    execute_values(
        cursor,
        """
        INSERT INTO snomed_concepts (snomed_code, description, is_active, version)
        VALUES %s
        ON CONFLICT (snomed_code) DO UPDATE SET
            is_active = EXCLUDED.is_active,
            version = EXCLUDED.version
        """,
        rows,
        page_size=10_000,
    )
    return len(rows)


def flush_descriptions(cursor, rows: list[tuple]) -> int:
    if not rows:
        return 0
    execute_values(
        cursor,
        """
        INSERT INTO snomed_descriptions (
            id, concept_id, term, type_id, language_code, is_active, effective_time
        )
        VALUES %s
        ON CONFLICT (id) DO UPDATE SET
            concept_id = EXCLUDED.concept_id,
            term = EXCLUDED.term,
            type_id = EXCLUDED.type_id,
            language_code = EXCLUDED.language_code,
            is_active = EXCLUDED.is_active,
            effective_time = EXCLUDED.effective_time
        """,
        rows,
        page_size=10_000,
    )
    return len(rows)


def flush_fsn_updates(cursor, rows: list[tuple]) -> int:
    if not rows:
        return 0
    execute_batch(
        cursor,
        """
        UPDATE snomed_concepts
        SET description = %s, semantic_tag = %s
        WHERE snomed_code = %s
        """,
        rows,
        page_size=10_000,
    )
    return len(rows)


def flush_relationships(cursor, rows: list[tuple]) -> int:
    if not rows:
        return 0
    execute_values(
        cursor,
        """
        INSERT INTO snomed_relationships (
            id, source_id, destination_id, type_id, relationship_group, is_active, effective_time
        )
        VALUES %s
        ON CONFLICT (id) DO UPDATE SET
            source_id = EXCLUDED.source_id,
            destination_id = EXCLUDED.destination_id,
            type_id = EXCLUDED.type_id,
            relationship_group = EXCLUDED.relationship_group,
            is_active = EXCLUDED.is_active,
            effective_time = EXCLUDED.effective_time
        """,
        rows,
        page_size=10_000,
    )
    return len(rows)


def main() -> None:
    load_dotenv()

    database_url = os.getenv("DATABASE_URL")
    snomed_dir = os.getenv("SNOMED_RF2_DIR")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required")
    if not snomed_dir:
        raise RuntimeError("SNOMED_RF2_DIR is required")

    term_dir = Path(snomed_dir)
    concept_file = term_dir / "sct2_Concept_Snapshot_INT_20260301.txt"
    description_file = term_dir / "sct2_Description_Snapshot-en_INT_20260301.txt"
    relationship_file = term_dir / "sct2_Relationship_Snapshot_INT_20260301.txt"

    for required in (concept_file, description_file, relationship_file):
        if not required.exists():
            raise FileNotFoundError(f"Missing RF2 file: {required}")

    t0 = time.perf_counter()
    conn = psycopg2.connect(database_url)
    conn.autocommit = False

    concept_ids: set[str] = set()
    inserted_concepts = 0
    inserted_descriptions = 0
    updated_fsns = 0
    inserted_relationships = 0

    try:
        with conn.cursor() as cur:
            print("Truncating SNOMED concept graph (cascade)...")
            cur.execute("TRUNCATE snomed_concepts CASCADE")
            conn.commit()

            print("Pass 1/3: Concepts")
            concept_batch: list[tuple] = []
            for row in iter_tsv_rows(concept_file):
                if row["active"] != "1":
                    continue
                concept_id = row["id"]
                concept_ids.add(concept_id)
                concept_batch.append((concept_id, "", True, "SNOMED-CT-20260301"))
                if len(concept_batch) >= BATCH_SIZE:
                    inserted_concepts += flush_concepts(cur, concept_batch)
                    conn.commit()
                    concept_batch.clear()
            inserted_concepts += flush_concepts(cur, concept_batch)
            conn.commit()

            print("Pass 2/3: Descriptions + FSN backfill")
            desc_batch: list[tuple] = []
            fsn_update_batch: list[tuple] = []
            for row in iter_tsv_rows(description_file):
                if row["active"] != "1":
                    continue
                concept_id = row["conceptId"]
                if concept_id not in concept_ids:
                    continue

                desc_batch.append(
                    (
                        int(row["id"]),
                        concept_id,
                        row["term"],
                        row["typeId"],
                        row["languageCode"],
                        True,
                        parse_effective_date(row["effectiveTime"]),
                    )
                )

                if row["typeId"] == FSN_TYPE_ID:
                    fsn = row["term"]
                    fsn_update_batch.append((fsn, extract_semantic_tag(fsn), concept_id))

                if len(desc_batch) >= BATCH_SIZE:
                    inserted_descriptions += flush_descriptions(cur, desc_batch)
                    conn.commit()
                    desc_batch.clear()
                if len(fsn_update_batch) >= BATCH_SIZE:
                    updated_fsns += flush_fsn_updates(cur, fsn_update_batch)
                    conn.commit()
                    fsn_update_batch.clear()

            inserted_descriptions += flush_descriptions(cur, desc_batch)
            updated_fsns += flush_fsn_updates(cur, fsn_update_batch)
            conn.commit()

            print("Pass 3/3: Relationships")
            rel_batch: list[tuple] = []
            for row in iter_tsv_rows(relationship_file):
                if row["active"] != "1":
                    continue
                rel_batch.append(
                    (
                        int(row["id"]),
                        row["sourceId"],
                        row["destinationId"],
                        row["typeId"],
                        int(row["relationshipGroup"]),
                        True,
                        parse_effective_date(row["effectiveTime"]),
                    )
                )
                if len(rel_batch) >= BATCH_SIZE:
                    inserted_relationships += flush_relationships(cur, rel_batch)
                    conn.commit()
                    rel_batch.clear()
            inserted_relationships += flush_relationships(cur, rel_batch)
            conn.commit()

            cur.execute("SELECT COUNT(*) FROM snomed_concepts")
            concept_count = int(cur.fetchone()[0])
            cur.execute("SELECT COUNT(*) FROM snomed_descriptions")
            description_count = int(cur.fetchone()[0])
            cur.execute("SELECT COUNT(*) FROM snomed_relationships")
            relationship_count = int(cur.fetchone()[0])

        elapsed = round(time.perf_counter() - t0, 2)
        print("\nSNOMED RF2 import complete")
        print(f"Elapsed seconds: {elapsed}")
        print(f"Inserted concepts: {inserted_concepts}")
        print(f"Inserted descriptions: {inserted_descriptions}")
        print(f"Updated FSN rows: {updated_fsns}")
        print(f"Inserted relationships: {inserted_relationships}")
        print("\nVerification counts")
        print(f"snomed_concepts: {concept_count}")
        print(f"snomed_descriptions: {description_count}")
        print(f"snomed_relationships: {relationship_count}")
        if concept_count <= 300_000:
            raise RuntimeError(
                "Concept count is below expected threshold (>300000). Check RF2 path/load."
            )
    finally:
        conn.close()


if __name__ == "__main__":
    main()
