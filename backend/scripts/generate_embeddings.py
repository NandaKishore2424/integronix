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
from sentence_transformers import SentenceTransformer

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is required in .env")

PAGE_SIZE     = 1000
ENCODE_BATCH  = 64
COMMIT_EVERY  = 1000   # one COPY + one join-UPDATE per flush


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



def _flush(update_cur, table: str, pk_col: str, pending: list[tuple]) -> None:
    """Bulk write: COPY rows into a temp stage table, then one join-UPDATE.

    Per-row UPDATEs cost a network round-trip each (~3-4 min per 1000 rows
    against Supabase). COPY streams the whole batch in one shot and the single
    UPDATE joins it server-side — the same batch lands in a few seconds.
    """
    from io import StringIO
    # SET LOCAL applies for the current transaction only — this survives
    # transaction-pooled connections where connection options are ignored.
    update_cur.execute("SET LOCAL statement_timeout = '300s'")
    buf = StringIO()
    for vec, pk in pending:
        buf.write(pk + "\t[" + ",".join(f"{x:.6f}" for x in vec) + "]\n")
    buf.seek(0)
    update_cur.execute("CREATE TEMP TABLE IF NOT EXISTS _emb_stage (pk text PRIMARY KEY, vec text)")
    update_cur.execute("TRUNCATE _emb_stage")
    update_cur.copy_expert("COPY _emb_stage (pk, vec) FROM STDIN", buf)
    update_cur.execute(
        f"UPDATE {table} t SET embedding = s.vec::vector FROM _emb_stage s WHERE t.{pk_col} = s.pk"
    )

def process_table(
    conn,
    *,
    table: str,
    pk_col: str,
    text_col: str,
    include_pk_in_text: bool,
    extra_where: str = "",
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
                  {extra_where}
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
                _flush(update_cur, table, pk_col, pending)
                conn.commit()
                total += len(pending)
                elapsed = round(time.perf_counter() - t0, 1)
                print(f"  [{table}] committed {total} embeddings — {elapsed}s elapsed")
                pending.clear()

        # flush remainder
        if pending:
            _flush(update_cur, table, pk_col, pending)
            conn.commit()
            total += len(pending)

    elapsed = round(time.perf_counter() - t0, 1)
    print(f"  [{table}] done — {total} embeddings in {elapsed}s")
    return total


def main() -> None:
    conn = psycopg2.connect(DATABASE_URL, options="-c statement_timeout=300000")
    conn.autocommit = False
    with conn.cursor() as cur:
        cur.execute("SET statement_timeout = '300s'")
    conn.commit()
    try:
        print("\nStep 1/2: ICD codes")
        icd_count = process_table(
            conn,
            table="icd_codes",
            pk_col="code",
            text_col="description",
            include_pk_in_text=True,
            # Only billable (leaf) codes can appear on a claim — the decision
            # node filters non-billable candidates anyway, and the Supabase
            # free tier (500 MB) cannot hold vectors for rows that can never win.
            extra_where="AND is_billable",
        )

        if os.getenv("EMBED_SNOMED") == "1":
            print("\nStep 2/2: SNOMED concepts")
            snomed_count = process_table(
                conn,
                table="snomed_concepts",
                pk_col="snomed_code",
                text_col="description",
                include_pk_in_text=False,
            )
        else:
            snomed_count = 0
            print("\nStep 2/2: SNOMED concepts — SKIPPED.")
            print("  379K vectors ≈ 600+ MB, which exceeds the Supabase free tier (500 MB).")
            print("  Set EMBED_SNOMED=1 to run it anyway on a larger plan.")
    finally:
        conn.close()

    print(f"\nEmbedding generation complete")
    print(f"icd_codes embedded:      {icd_count}")
    print(f"snomed_concepts embedded: {snomed_count}")
    print(f"\nNext step: run migrations/schema/013_rebuild_snomed_ivfflat.sql in Supabase SQL Editor")


if __name__ == "__main__":
    main()
