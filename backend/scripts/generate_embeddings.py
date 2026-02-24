#!/usr/bin/env python3
"""
scripts/generate_embeddings.py
Generates 384-dim embeddings for all ICD codes + SNOMED concepts
that have NULL embeddings and uploads them to Supabase via REST API.

Run once after running migrations 001-010 and seeding data.

Usage:
    cd backend
    source venv/bin/activate
    python3 scripts/generate_embeddings.py
"""
import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from sentence_transformers import SentenceTransformer
from config import settings

SUPABASE_URL = settings.supabase_url
SUPABASE_KEY = settings.supabase_service_key or settings.supabase_anon_key
HEADERS = {
    "apikey":        settings.supabase_anon_key,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type":  "application/json",
    "Prefer":        "return=minimal",
}

print("⏳ Loading sentence-transformers model (all-MiniLM-L6-v2)...")
model = SentenceTransformer("all-MiniLM-L6-v2")
print("✅ Model loaded")


def embed(text: str) -> list[float]:
    return model.encode(text, normalize_embeddings=True).tolist()


async def fetch_rows(client: httpx.AsyncClient, table: str, select: str, limit: int = 500) -> list[dict]:
    r = await client.get(
        f"{SUPABASE_URL}/rest/v1/{table}",
        params={"select": select, "embedding": "is.null", "limit": str(limit)},
        headers=HEADERS,
    )
    return r.json() if r.status_code == 200 else []


async def update_embedding(client: httpx.AsyncClient, table: str, pk_col: str, pk_val: str, embedding: list[float]):
    r = await client.patch(
        f"{SUPABASE_URL}/rest/v1/{table}",
        params={pk_col: f"eq.{pk_val}"},
        json={"embedding": embedding},
        headers=HEADERS,
    )
    return r.status_code in (200, 204)


async def main():
    async with httpx.AsyncClient(timeout=30.0) as client:

        # ── ICD codes ─────────────────────────────────────────────────────────
        print("\n🔎 Fetching ICD codes with NULL embeddings...")
        icd_rows = await fetch_rows(client, "icd_codes", "code,description")
        print(f"   Found {len(icd_rows)} ICD codes to embed")

        for i, row in enumerate(icd_rows):
            text = f"{row['code']} {row['description']}"
            embedding = embed(text)
            ok = await update_embedding(client, "icd_codes", "code", row["code"], embedding)
            status = "✅" if ok else "❌"
            print(f"   {status} [{i+1}/{len(icd_rows)}] {row['code']} — {row['description'][:50]}")

        # ── SNOMED concepts ────────────────────────────────────────────────────
        print("\n🔎 Fetching SNOMED concepts with NULL embeddings...")
        snomed_rows = await fetch_rows(client, "snomed_concepts", "snomed_code,description")
        print(f"   Found {len(snomed_rows)} SNOMED concepts to embed")

        for i, row in enumerate(snomed_rows):
            text = row["description"]
            embedding = embed(text)
            ok = await update_embedding(client, "snomed_concepts", "snomed_code", row["snomed_code"], embedding)
            status = "✅" if ok else "❌"
            print(f"   {status} [{i+1}/{len(snomed_rows)}] {row['snomed_code']} — {row['description'][:50]}")

    print("\n🏆 Embedding generation complete!")
    print("   Node 5 (embedding fallback) is now ready to use.")


if __name__ == "__main__":
    asyncio.run(main())
