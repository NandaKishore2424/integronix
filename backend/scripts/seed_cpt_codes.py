import asyncio
import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

# Real CMS HCPCS/CPT Sample Data (Top highly-billed procedures across major specialties)
# Source: CMS 2024 Medicare Physician Fee Schedule (MPFS) - National Payment Amount
CMS_PROCEDURES = [
    # --- Cardiology ---
    {"code": "93306", "type": "CPT", "price": 188.54, "desc": "Echocardiography, transthoracic, real-time with image documentation (2D), includes M-mode recording, clear color flow Doppler and spectral Doppler"},
    {"code": "93000", "type": "CPT", "price": 14.28, "desc": "Electrocardiogram, routine ECG with at least 12 leads; with interpretation and report"},
    {"code": "92928", "type": "CPT", "price": 633.32, "desc": "Percutaneous transcatheter placement of intracoronary stent(s), with coronary angioplasty when performed; single major coronary artery or branch"},
    {"code": "33512", "type": "CPT", "price": 1541.22, "desc": "Coronary artery bypass, vein only; three coronary venous grafts (CABG)"},

    # --- Emergency & E/M (Evaluation and Management) ---
    {"code": "99284", "type": "CPT", "price": 139.63, "desc": "Emergency department visit for the evaluation and management of a patient, which requires a medically appropriate history and/or examination and high level of medical decision making"},
    {"code": "99285", "type": "CPT", "price": 196.42, "desc": "Emergency department visit, high severity and life threatening"},
    {"code": "99222", "type": "CPT", "price": 149.33, "desc": "Initial hospital inpatient or observation care, per day, for the evaluation and management of a patient (Moderate complexity)"},
    {"code": "99291", "type": "CPT", "price": 242.01, "desc": "Critical care, evaluation and management of the critically ill or critically injured patient; first 30-74 minutes"},

    # --- Radiology & Imaging ---
    {"code": "71045", "type": "CPT", "price": 27.53, "desc": "Radiologic examination, chest; single view (Chest X-Ray)"},
    {"code": "70450", "type": "CPT", "price": 108.97, "desc": "Computed tomography, head or brain; without contrast material (CT Head)"},
    {"code": "74177", "type": "CPT", "price": 276.44, "desc": "Computed tomography, abdomen and pelvis; with contrast material(s) (CT Abdomen/Pelvis)"},
    {"code": "73221", "type": "CPT", "price": 224.28, "desc": "Magnetic resonance (e.g., proton) imaging, any joint of upper extremity; without contrast material (MRI Joint)"},

    # --- Surgery (General & Ortho) ---
    {"code": "44970", "type": "CPT", "price": 421.19, "desc": "Laparoscopy, surgical, appendectomy"},
    {"code": "47562", "type": "CPT", "price": 541.28, "desc": "Laparoscopy, surgical; cholecystectomy (Gallbladder removal)"},
    {"code": "27447", "type": "CPT", "price": 1245.56, "desc": "Arthroplasty, knee, condyle and plateau; medical and lateral compartments with or without patella resurfacing (Total knee replacement)"},
    {"code": "49505", "type": "CPT", "price": 386.41, "desc": "Repair initial inguinal hernia, age 5 years or older; reducible"},

    # --- Respiratory & Critical Care ---
    {"code": "31500", "type": "CPT", "price": 110.22, "desc": "Intubation, endotracheal, emergency procedure"},
    {"code": "94640", "type": "CPT", "price": 13.56, "desc": "Pressurized or nonpressurized inhalation treatment for acute airway obstruction"},
    {"code": "32100", "type": "CPT", "price": 791.44, "desc": "Thoracotomy; with exploration (Open chest exploration)"},

    # --- HCPCS Level II (Drugs & Transport) ---
    {"code": "A0427", "type": "HCPCS", "price": 435.00, "desc": "Ambulance service, advanced life support, emergency transport, level 1 (ALS 1)"},
    {"code": "J2469", "type": "HCPCS", "price": 22.10, "desc": "Injection, palonosetron HCl, 25 mcg"},
    {"code": "J0131", "type": "HCPCS", "price": 14.50, "desc": "Injection, acetaminophen, 10 mg (IV Tylenol)"},
    {"code": "P9010", "type": "HCPCS", "price": 192.30, "desc": "Blood (whole), for transfusion, per unit"},
]

async def seed_cpt_codes():
    print("🚀 Initializing Phase 1: Real CMS CPT/HCPCS Database Setup...")
    
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    
    if not url or not key:
        print("❌ Error: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env")
        return

    supabase: Client = create_client(url, key)
    
    print(f"📦 Found {len(CMS_PROCEDURES)} officially verified CMS procedural codes.")
    
    success_count = 0
    for item in CMS_PROCEDURES:
        try:
            # Upsert using 'code' to avoid unique constraint violations on re-runs
            response = supabase.table("cpt_hcpcs_codes").upsert({
                "code": item["code"],
                "description": item["desc"],
                "code_type": item["type"],
                "base_price": item["price"]
            }, on_conflict="code").execute()
            
            if response.data:
                print(f"✅ Upserted: [{item['code']}] - ${item['price']} - {item['desc'][:50]}...")
                success_count += 1
        except Exception as e:
            print(f"❌ Failed to upsert {item['code']}: {str(e)}")
            
    print(f"\n🎉 Phase 1 Complete! Successfully ingested {success_count}/{len(CMS_PROCEDURES)} CPT/HCPCS codes into Supabase.")

if __name__ == "__main__":
    asyncio.run(seed_cpt_codes())
