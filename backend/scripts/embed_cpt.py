import asyncio
import os
from dotenv import load_dotenv
from supabase import create_client, Client
from sentence_transformers import SentenceTransformer

load_dotenv()

async def generate_cpt_embeddings():
    print("🚀 Initializing Phase 2: Generating AI Vector Embeddings for CPT/HCPCS data...")

    # 1. Connect to Database
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    
    if not url or not key:
        print("❌ Error: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env")
        return

    supabase: Client = create_client(url, key)

    # 2. Fetch records that need embeddings (where vector is null)
    # Even though all are null now, this makes the script idempotent and scalable
    print("📥 Fetching raw procedural data from Supabase (finding records missing embeddings)...")
    response = supabase.table("cpt_hcpcs_codes").select("id, code, description").is_("embedding", "null").execute()
    
    records = response.data
    if not records:
        print("✅ No records found requiring embeddings. Database is fully up to date.")
        return
        
    print(f"🎯 Found {len(records)} codes that need processing.")

    # 3. Load Local Open-Source AI Model
    print("🧠 Loading local sentence-transformer model (all-MiniLM-L6-v2)...")
    # This guarantees HIPAA compliance because data never leaves the server to an external API like OpenAI
    model = SentenceTransformer("all-MiniLM-L6-v2")

    # 4. Generate Embeddings efficiently in a batch
    print(f"⚙️ Generating 384-dimensional semantic vectors for {len(records)} descriptions...")
    
    # We embed a combination of the code and description for maximum semantic richness
    # e.g., "CPT 93306: Echocardiography, transthoracic..."
    texts_to_embed = [f"{record['code']} - {record['description']}" for record in records]
    
    # model.encode returns a numpy array. We convert to list for JSON serialization.
    embeddings = model.encode(texts_to_embed).tolist()

    # 5. Bulk Update Database
    print("📤 Uploading generated vectors back to Supabase...")
    
    success_count = 0
    for idx, record in enumerate(records):
        try:
            vector_data = embeddings[idx]
            
            # Update the specific row with its new vector
            supabase.table("cpt_hcpcs_codes").update({"embedding": vector_data}).eq("id", record["id"]).execute()
            success_count += 1
            if success_count % 5 == 0 or success_count == len(records):
                print(f"   [Progress]: {success_count}/{len(records)} vectors stored.")
        except Exception as e:
            print(f"❌ Failed to update vector for {record['code']}: {str(e)}")

    print(f"\n🎉 Phase 2 Complete! Successfully weaponized {success_count} codes for AI semantic search.")

if __name__ == "__main__":
    asyncio.run(generate_cpt_embeddings())
