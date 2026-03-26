# SNOMED CT MLDS Ingestion & Vector Embedding Guide

**For the Data Engineer/GPU Operator (Via Antigravity)**
This document explains the complete, A-to-Z process for migrating the Integronix AI pipeline from a "mock" 20-row vocabulary to the full, production-grade SNOMED CT international database.

Because you have access to a dedicated GPU (Minisforum AMD, 32GB RAM), you are capable of handling the bottleneck of this process: **Generating 384-dimensional AI Vector Embeddings for 350,000+ medical concepts.**

---

## 1. The Raw Data (What We Have)
The user has downloaded the official `SnomedCT_InternationalRF2_PRODUCTION_20260301T120000Z` ZIP file. 

Inside this release, you will see a `Full` directory and a `Snapshot` directory.
- `Full`: Contains every historical edit since the database's inception. **We ignore this.**
- `Snapshot`: Contains only the absolute latest, active/inactive state of every component as of March 1, 2026. **We will exclusively parse the files in `Snapshot/Terminology/`.**

### The 3 Core Files We Need:
1. **`sct2_Concept_Snapshot_...txt` (31 MB):** Contains ~350,000 core concept IDs and their `active/inactive` status.
2. **`sct2_Description_Snapshot...txt` (227 MB):** Contains ~1.5 million text strings. Every concept has one "Fully Specified Name" (FSN) and multiple alternative "Synonyms". 
3. **`sct2_Relationship_Snapshot_...txt` (396 MB):** Contains ~1.5 million parent-child relationships (e.g., mapping that "NSTEMI" IS-A "Heart Disease").

---

## 2. The Target Database Schema
Your Supabase (PostgreSQL) database is pre-configured with three tables to receive this data. (See `migrations/schema/010_snomed_rf2.sql` and `003_medical_ontology.sql`).

1. **`snomed_concepts`**:
   - `snomed_code` (PK) -> Comes from `sct2_Concept` ID.
   - `description` -> Comes from the primary FSN in `sct2_Description`.
   - `embedding` -> A `vector(384)` column for semantic similarity search.
   - `is_active` -> From `active` in `sct2_Concept`.

2. **`snomed_descriptions`**:
   - Holds the 1.5 million alternative text strings (Synonyms) so our standard `ilike` text-search fallback can catch doctor slang.

3. **`snomed_relationships`**:
   - Holds the IS-A medical hierarchy tree.

---

## 3. What Are Vectors & Embeddings? (Why are you needed?)
In AI, computers do not understand that "Patient's ticker stopped working" and "Cardiac Arrest" mean the same thing. Standard SQL text searches (`ilike "ticker"`) will return 0 results.

**Embeddings** solve this. 
An AI model (like `SentenceTransformers` using `all-MiniLM-L6-v2`) reads a medical phrase and translates its contextual *meaning* into an array of 384 numbers (a vector). 

When the Integronix AI searches the database, Supabase calculates the mathematical distance between vectors (`pgvector`). It can map a doctor's messy note to the exact SNOMED concept with 99% accuracy—even if they share exactly zero alphabetical letters.

### The Bottleneck
Running `SentenceTransformers` locally on a standard laptop to convert 350,000 sentences into vectors takes **20 to 30 hours** using just a CPU. 

**Because you have a GPU with 32GB of RAM, you can process these thousands of strings in batches, offloading the tensor operations to your AMD GPU. You can reduce this ingestion time from 30 hours to roughly 30 minutes.**

---

## 4. The Execution Plan (What You Need to Do)

As the Antigravity system operator on the GPU machine, you will need to build and execute a Python ETL (Extract, Transform, Load) script. 

### Step 1: The ETL Pipeline Script (`backend/scripts/import_snomed_rf2.py`)
Have Antigravity write a highly optimized Python script that:
1. Opens the `sct2_*.txt` files using a memory-safe line-by-line reader (generator).
2. Filters out any rows where `active == 0`.
3. Merges the concepts with their Fully Specified Names.
4. Uses `psycopg2.extras.execute_values()` or native `COPY` commands to bulk-insert the relational textual data into Supabase in blocks of 50,000 rows. (Do this *before* generating embeddings to ensure the data is safe).

### Step 2: The GPU Vector Generation Pipeline
Once the base tables are populated:
1. The script should pull the `description` text from `snomed_concepts` in batches of 1,000.
2. Ensure PyTorch is utilizing the AMD GPU (DirectML or ROCm depending on your driver setup) rather than failing back to the CPU.
3. Pass the texts through `SentenceTransformer('all-MiniLM-L6-v2')`.
4. Run an `UPDATE` SQL operation to save the generated `[0.12, -0.45...]` array into the `embedding` column of the `snomed_concepts` table.

### Step 3: Verification
1. Run a `COUNT(*)` in the database to verify ~350,000 concepts exist.
2. Run a pure semantic vector search in `snomed_resolver.py` to prove that the AMD GPU successfully computed the arrays. (e.g. searching "Broken leg bone" should structurally return the formal "Fracture of tibia" or "Fracture of femur" FSN concept without using `ilike`).

---

## 5. Expectations & Gotchas
- **RAM Limits**: Even with 32GB RAM, pulling all 1.5 million relationships into a pandas dataframe will probably stall or swap. **Stream the TSV files block-by-block**.
- **Supabase Timeouts**: If you try to push 350,000 vectors in a single transaction, the cloud database will timeout. Always commit in batches `(batch_size=5000)`.
- **Delete the Mock Data**: Ensure your script runs a `TRUNCATE snomed_concepts CASCADE;` (while honoring the `snomed_icd_map` foreign keys) to wipe out the 20 fake prototype rows before inserting the production data.

Good luck!
