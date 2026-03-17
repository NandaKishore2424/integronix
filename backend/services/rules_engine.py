from typing import Dict, Any, Tuple
from logger import get_logger

log = get_logger(__name__)

def evaluate_claim(claim_data: Dict[str, Any], patient_name: str) -> Tuple[bool, str]:
    """
    Evaluates a claim payload against hardcoded deterministic payer rules.
    Returns (is_approved, reason_if_denied)
    
    If is_approved is False, the claim should be auto-denied.
    """
    log.info("rules_engine_evaluating", patient=patient_name)
    
    try:
        # 1. AI Confidence / Clinical Risk Check
        risk_score = claim_data.get("risk_score", 0)
        if risk_score > 85:
            return False, f"AUTO-DENIED: Integronix AI Risk Score ({risk_score}/100) exceeds threshold. Please review clinical justification."
            
        # 2. Demographic Constraint Checks (Mock deterministic rules)
        # In a real engine, this would check against an ICD/CPT master database.
        cpt_codes = claim_data.get("cpt_codes", [])
        cpt_strings = [c.get("cpt_code", "") for c in cpt_codes]
        
        # Example Rule: 58150 (Total abdominal hysterectomy) requires a female patient.
        # We will weakly infer gender by name for demonstration purposes, or assume failure.
        male_names = ["john", "james", "robert", "michael", "william", "david"]
        first_name = patient_name.split(" ")[0].lower()
        
        if "58150" in cpt_strings and first_name in male_names:
            return False, "AUTO-DENIED: CPT 58150 (Hysterectomy) conflicts with inferred patient demographics (Male)."
            
        # Example Rule: 59400 (Routine obstetric care)
        if "59400" in cpt_strings and first_name in male_names:
            return False, "AUTO-DENIED: CPT 59400 (Obstetric care) conflicts with inferred patient demographics (Male)."
            
        # 3. Medical Necessity Check (Basic)
        # Ensure there is at least one diagnosis code billed.
        icd_codes = claim_data.get("icd_codes", [])
        if len(cpt_codes) > 0 and len(icd_codes) == 0:
            return False, "AUTO-DENIED: Claim contains procedures (CPT) without supporting diagnoses (ICD-10)."
            
        return True, "PASSED"
        
    except Exception as e:
        log.error("rules_engine_failed", error=str(e))
        return False, "AUTO-DENIED: System error during rule evaluation."
