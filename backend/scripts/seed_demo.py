"""
backend/scripts/seed_demo.py
Creates demo organizations and users across all 5 roles for testing.
Run from the backend directory using: python -m scripts.seed_demo
"""

import asyncio
from supabase import create_client, Client
import random
import string

from config import settings

# Must use service key to create auth users
url: str = settings.supabase_url
key: str = settings.supabase_service_key or settings.supabase_anon_key
sb: Client = create_client(url, key)

def rand_slug(name: str):
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
    return f"{name.lower().replace(' ', '-')}-{suffix}"

async def seed():
    print("🌱 Starting Demo Seed...")

    # 1. Create Organizations
    print("1️⃣  Creating Organizations...")
    hospital_res = sb.table("organizations").insert({
        "name": "Apollo Hospitals",
        "slug": rand_slug("apollo"),
        "type": "hospital"
    }).execute()
    apollo_id = hospital_res.data[0]["id"]

    payer_res = sb.table("payers").insert({
        "name": "Star Health Insurance",
        "payer_type": "commercial"
    }).execute()
    # Note: Payers have their own table (payers) and are ALSO organizations?
    # Wait, in this schema, payers might just be organizations. Let's check `payers` vs `organizations`.
    # Let's insert into both or just what is needed.
    # Ah, the user's table relies on organizations.id.
    insurance_org_res = sb.table("organizations").insert({
        "name": "Star Health Insurance",
        "slug": rand_slug("star"),
        "type": "insurance_payer"
    }).execute()
    star_id = insurance_org_res.data[0]["id"]

    # 2. Define Demo Users
    demo_users = [
        # Hospital side
        {"email": "admin@apollo.com", "name": "Hospital Admin", "role": "admin", "org_id": apollo_id},
        {"email": "coder@apollo.com", "name": "Jane Coder", "role": "coder", "org_id": apollo_id},
        {"email": "auditor@apollo.com", "name": "Bob Auditor", "role": "auditor", "org_id": apollo_id},
        {"email": "rcm@apollo.com", "name": "Alice RCM", "role": "rcm", "org_id": apollo_id},
        
        # Payer side
        {"email": "admin@starhealth.com", "name": "Insurance Admin", "role": "admin", "org_id": star_id},
        {"email": "adjudicator@starhealth.com", "name": "Dave Adjudicator", "role": "payer", "org_id": star_id},
    ]

    print("2️⃣  Creating Users...")
    for u in demo_users:
        target_email = u["email"]
        password = "password123"
        
        # Try to delete if existing to make script idempotent
        # Admin api for deletion requires UID, so let's just create and catch if it exists
        try:
            auth_res = sb.auth.admin.create_user({
                "email": target_email,
                "password": password,
                "email_confirm": True
            })
            auth_uid = auth_res.user.id
            
            # Insert into public.users
            sb.table("users").insert({
                "auth_id": auth_uid,
                "organization_id": u["org_id"],
                "email": target_email,
                "full_name": u["name"],
                "role": u["role"]
            }).execute()
            print(f"✅ Created {u['role']} - {target_email} (Password: {password})")
            
        except Exception as e:
            print(f"⚠️  Skipped {target_email} - likely already exists: {e}")

    print("\n🎉 Seeding Complete! You can now log into the frontend with the emails above.")
    print("All passwords are: password123")

if __name__ == "__main__":
    asyncio.run(seed())
