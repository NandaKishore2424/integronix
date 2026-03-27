import asyncio
import os
from supabase import create_client
import httpx

# The supabase python client doesn't directly support raw SQL execution easily.
# Let's use standard postgres via psycopg if installed, or just call the REST API if needed.
# Actually, the easiest way to run raw SQL in a python script with Supabase 
# is to use psycopg2 or perform an API call to the pgtap or similar endpoints,
# BUT wait! We can just use the python `psycopg2` driver. Is it available?
import subprocess

with open("migrations/schema/019_payer_org_link.sql", "r") as f:
    sql = f.read()

# Since Integronix uses FastAPI, sqlalchemy/asyncpg is highly likely installed.
# We will just write a standard quick asyncpg snippet.
import asyncpg

async def run():
    # standard local supabase postgres url
    conn = await asyncpg.connect('postgresql://postgres:postgres@localhost:54322/postgres')
    await conn.execute(sql)
    print("Migration applied successfully!")
    await conn.close()

asyncio.run(run())
