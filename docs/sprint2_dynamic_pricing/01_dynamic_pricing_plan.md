# Sprint 2: Dynamic Pricing & Org Multipliers

**Goal:** Implement real-world Revenue Cycle Management (RCM) economics by applying hospital-specific pricing multipliers to the base CMS procedural rates.

## Phase 1: Database Updates
- [x] Update the `org_settings` Supabase table to include a `cpt_pricing_multiplier` column.
- [x] Set demo multipliers (e.g., "City General Hospital" = 1.0, "Premium Care Institute" = 1.8).

> **Phase 1 Implementation Notes (Senior Database Engineer Log):**
> * **Schema Alteration:** Added a `cpt_pricing_multiplier` numeric column to the `org_settings` table via `022_dynamic_pricing_multiplier.sql`. 
> * **Data Integrity:** Added a `CHECK` constraint ensuring the multiplier stays within realistic bounds (0.1 to 10.0) to prevent astronomical math errors in the RCM pipeline.
> * **Demo Seed:** Included `UPDATE` statements to automatically apply the premium 1.8x multiplier to "Premium" hospitals and a standard 1.2x to "City" hospitals upon running the migration, perfectly setting up the demo environment.
## Phase 2: Pipeline Financial Engine
- [x] **Node 6 (financial_calculator.py):** Create a new node at the very end of the pipeline.
- [x] Retrieve the current organization's `cpt_pricing_multiplier`.
- [x] Iterate through all resolved CPT codes from the `cpt_resolver` node.
- [x] Multiply the `base_price` by the `multiplier` to get the `estimated_hospital_revenue`.
- [x] Aggregate and calculate the `Total Estimated Reimbursement` for the entire hospital visit.
- [x] Update `CodingState` and `routes/code.py` to output the final financial object.

> **Phase 2 Implementation Notes (Senior AI Engineer Log):**
> * **Node Architecture:** Built `agents/financial_calculator.py` as a idempotent post-processing node. It leverages the previously resolved CPT array to perform hospital-specific billing math.
> * **Multi-Tier Fallback:** Implemented a robust lookup strategy that tries to find the specific `org_id` multiplier first, falling back to a demo-wide default (1.0x) to ensure the pipeline never crashes during testing.
> * **API Schema Expansion:** Updated `models.py` and `routes/code.py` to pass the `financial_summary` object (total revenue + line items) all the way to the frontend.

## Phase 3: Frontend Integration
- [x] Ensure the Next.js `ResultsPanel` dynamically displays the CPT codes alongside the ICD diagnoses.
- [x] Create a `CptCodeList` component to render itemized procedural costs.
- [x] Update the main KPI section to show "Estimated Hospital Revenue" using the calculated total.
- [x] Add a demo "Hospital Context" selector to show the difference between multipliers (1.2x vs 1.8x).

> **Phase 3 Implementation Notes (Senior UI/UX Engineer Log):**
> * **Financial Dashboard:** Integrated the `IndianRupee` currency context and itemized CPT charges into the results view. The UI now clearly shows the "Base Price" vs "Gross Charge" based on the multiplier.
> * **Interactive Demo Mode:** Added a "Demo Context" dropdown in the analysis sub-nav. This allows judges/users to immediately see how the exact same documentation generates different revenue based on the hospital's chargemaster settings.
> * **Type Safety:** Updated `frontend/src/types/coding.ts` to ensure full end-to-end type parity with the backend RCM engine.

---
**Sprint 2 Status:** ✅ COMPLETED
**Next Steps:** Proceed to Sprint 3 (Payer Integration & Status Tracking).
