# The Integronix Story: End-to-End Revenue Cycle Management (RCM)

This story maps out the real-world interactions between a Healthcare Provider (Hospital) and a Health Insurance Company (Payer) on the Integronix platform. It defines the product vision and dictates our upcoming dev sprints.

---

## 🏗️ Chapter 1: Hospital Onboarding & Configuration
**City General Hospital (CGH)** decides they are losing too much money to billing errors and signs up for Integronix.

1. **Organization Setup:** The Hospital Admin creates an Organization account for CGH. They set up branches (e.g., "Downtown Campus", "North Wing") and invite users with specific roles: Doctors (who upload documents) and Medical Coders (who review the AI's work).
2. **The Rules Engine (Sprint 2):** CGH configures their `org_settings`. 
   - **Coding Standard:** They choose ICD-10 for diagnoses.
   - **The Pricing Multiplier (Chargemaster):** Because CGH is a standard city hospital, they set their `cpt_pricing_multiplier` to `1.2`. This means they charge 20% more than the national CMS base rate to cover their specific overhead.

---

## 🏥 Chapter 2: The Patient Encounter & AI Coding
A patient, John Doe, is admitted to CGH for severe chest pain. Dr. Smith treats him, performs an Echocardiogram, stablizes him, and writes a messy, unstructured Discharge Summary PDF.

1. **Document Upload:** Coder Jane (at CGH) takes the PDF and uploads it to the Integronix Dashboard.
2. **AI Processing:** 
   - Integronix's LangGraph pipeline extracts the diagnosis: *Acute Systolic Heart Failure*. It uses the WHO API to resolve this to **ICD-10 I50.21**.
   - It extracts the procedure: *Echocardiogram*. It uses the local vector semantic search to map this to **CPT 93306**.
3. **The Financial Engine (Sprint 2):** 
   - Integronix knows the CMS base rate for CPT 93306 is $188.54.
   - It applies CGH's multiplier: `$188.54 * 1.2 = $226.25`. 
   - The dashboard shows Jane the **Estimated Gross Hospital Revenue: $226.25**.

---

## ✉️ Chapter 3: The Claim Submission to the Payer
CGH is happy with the AI's coding. Jane clicks "Approve & Submit Claim".

1. **FHIR Generation:** Integronix wraps the ICD code, CPT code, and Gross Charge into a standard healthcare data format (FHIR or ASC X12 837).
2. **Transmission:** The claim is sent to John Doe's insurance company: **Star Health Insurance (The Payer)**.

---

## ⚖️ Chapter 4: Payer Adjudication (The Verdict)
This is where the money is actually decided. Star Health Insurance receives the claim for $226.25. 

Payers use platforms like Integronix on the *backend* to aggressively audit claims and save money. In our system, the claim's status will change based on three scenarios:

### Scenario A: Clean Claim (Status: PAID)
- Star Health's automated rules see that the Echo (93306) perfectly matches the Diagnosis (I50.21). It is medically necessary.
- **Result:** Status updates to exactly what was billed (or the max contracted rate). CGH receives the money.

### Scenario B: Contractual Adjustment (Status: PARTIALLY PAID)
- The medical necessity is fine, but Star Health has a pre-signed contract with CGH that says: *"We only pay a maximum of $200.00 for an Echocardiogram, no matter what your hospital's gross charge is."*
- **Result:** Star Health pays $200.00. The remaining $26.25 is swallowed by the hospital as a "Write-Off" or "Contractual Adjustment." The patient is not billed for the difference.

### Scenario C: Clinical Denial / Upcoding (Status: DENIED)
- Star Health runs Integronix's **Risk & Audit engine**. The engine scans the original text and flags a **Discrepancy (Overcoding)**. 
- *Reason:* The hospital billed for a high-severity emergency visit (CPT 99285), but the doctor's notes only described a regular, low-severity consultation. 
- **Result:** Star Health denies the claim entirely. CGH gets $0 and must either appeal the decision, rewrite the medical chart, or swallow the loss.

---

## 🚀 How This Maps to Our Next Sprints
To make this story a reality in our Hackathon prototype, here is the feature roadmap:

**Sprint 2: The Hospital Financial Engine**
- Build the Org Settings and Pricing Multiplier.
- Calculate the "Gross Charge" based on the CMS Base Price * Multiplier.

**Sprint 3: The Payer Mechanics (Adjudication)**
- Build a "Claims / Case Status" pipeline (`Draft` -> `Submitted` -> `Paid` / `Partially Paid` / `Denied`).
- Add a "Payer Contracted Rate" logic override (Scenario B).
- Connect the Audit Discrepancy node to automatically trigger Denials (Scenario C).
