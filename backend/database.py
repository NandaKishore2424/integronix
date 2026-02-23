import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

_pool = None


async def get_db_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            host=os.getenv("SUPABASE_HOST"),
            database=os.getenv("SUPABASE_DB", "postgres"),
            user=os.getenv("SUPABASE_USER", "postgres"),
            password=os.getenv("SUPABASE_PASSWORD"),
            port=int(os.getenv("SUPABASE_PORT", 5432)),
            ssl="require",
            min_size=1,
            max_size=10,
            command_timeout=10,
            timeout=5,        # fail fast — 5 second connection timeout
        )
    return _pool


async def close_db_pool():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
