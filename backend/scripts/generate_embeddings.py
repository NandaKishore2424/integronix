#!/usr/bin/env python3
"""
Generate embeddings for ICD codes + SNOMED concepts with NULL embeddings.

Uses psycopg2 direct connection for updates (avoids PostgREST NOT NULL restrictions).
Fetches rows in pages of 1000, encodes in batches of 64 on CPU, commits every 5000.

Usage:
    cd backend
    source venv/bin/activate
    python3 scripts/generate_embeddings.py
"""
from __future__ import annotations

import os
import sys
import time

# Add backend to path so config is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import psycopg2
from psycopg2.extras import execute_batch
from sentence_transformers import SentenceTransformer

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is required in .env")

PAGE_SIZE     = 1000
ENCODE_BATCH  = 64
COMMIT_EVERY  = 5000


print("Loading model all-MiniLM-L6-v2 on CPU...")
MODEL = SentenceTransformer("all-MiniLM-L6-v2")
print("Model ready")


def encode(texts: list[str]) -> list[list[float]]:
    return MODEL.encode(
        texts,
        batch_size=ENCODE_BATCH,
        normalize_embeddings=True,
        show_progress_bar=False,
    ).tolist()


def process_table(
    conn,
    *,
    table: str,
    pk_col: str,
    text_col: str,
    include_pk_in_text: bool,
) -> int:
    total = 0
    t0 = time.perf_counter()
    pending: list[tuple] = []   # (embedding_list, pk_value)

    with conn.cursor() as fetch_cur, conn.cursor() as update_cur:
        last_pk = ""
        page = 0
        while True:
            fetch_cur.execute(
                f"""
                SELECT {pk_col}, {text_col}
                FROM {table}
                WHERE embedding IS NULL
                  AND {pk_col} > %s
                ORDER BY {pk_col}
                LIMIT %s
                """,
                (last_pk, PAGE_SIZE),
            )
            rows = fetch_cur.fetchall()
            if not rows:
                break

            page += 1
            pks   = [r[0] for r in rows]
            texts = [
                f"{r[0]} {r[1] or ''}".strip() if include_pk_in_text else (r[1] or "")
                for r in rows
            ]

            vectors = encode(texts)
            for pk, vec in zip(pks, vectors):
                pending.append((vec, pk))

            last_pk = pks[-1]

            if len(pending) >= COMMIT_EVERY:
                execute_batch(
                    update_cur,
                    f"UPDATE {table} SET embedding = %s::vector WHERE {pk_col} = %s",
                    pending,
                    page_size=1000,
                )
                conn.commit()
                total += len(pending)
                elapsed = round(time.perf_counter() - t0, 1)
                print(f"  [{table}] committed {total} embeddings — {elapsed}s elapsed")
                pending.clear()

        # flush remainder
        if pending:
            execute_batch(
                update_cur,
                f"UPDATE {table} SET embedding = %s::vector WHERE {pk_col} = %s",
                pending,
                page_size=1000,
            )
            conn.commit()
            total += len(pending)

    elapsed = round(time.perf_counter() - t0, 1)
    print(f"  [{table}] done — {total} embeddings in {elapsed}s")
    return total


def main() -> None:
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    try:
        print("\nStep 1/2: ICD codes")
        icd_count = process_table(
            conn,
            table="icd_codes",
            pk_col="code",
            text_col="description",
            include_pk_in_text=True,
        )

        print("\nStep 2/2: SNOMED concepts")
        snomed_count = process_table(
            conn,
            table="snomed_concepts",
            pk_col="snomed_code",
            text_col="description",
            include_pk_in_text=False,
        )
    finally:
        conn.close()

    print(f"\nEmbedding generation complete")
    print(f"icd_codes embedded:      {icd_count}")
    print(f"snomed_concepts embedded: {snomed_count}")
    print(f"\nNext step: run migrations/schema/013_rebuild_snomed_ivfflat.sql in Supabase SQL Editor")


if __name__ == "__main__":
    main()
