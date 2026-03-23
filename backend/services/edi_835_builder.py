"""
backend/services/edi_835_builder.py

ANSI ASC X12 EDI 835 (Healthcare Claim Payment/Advice) builder.

The EDI 835 is a payer's structured response to a submitted claim.
It is generated AFTER adjudication (status: PAID, PARTIALLY_PAID, or DENIED).

X12 835 transaction set overview
----------------------------------
ISA / GS / ST (transaction set header 835)
BPR  – Beginning of Payment                 (total paid amount, currency)
TRN  – Trace Number                         (claim UUID)
REF  – Payer-specific reference
DTM  – Payment date
N1*PR  – Payer name
N1*PE  – Provider / hospital name
CLP  – Claim-Level Payment summary
       (CLM01=claim_id, CLM02=status_code, CLM03=billed, CLM04=paid)
NM1*QC – Patient name
SVC  – Service line (CPT code, billed, paid per item)
CAS  – Claim Adjustment Segment              (contractual write-off)
SE / GE / IEA – Trailers

Segment / element delimiters follow the same convention as edi_837_builder:
  Segment terminator : ~
  Element separator  : *
  Sub-element sep    : :
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

_SEG_TERM = "~"
_ELEM_SEP = "*"
_SUBELEMENT_SEP = ":"
_SENDER_ID = "INTGRNX01"
_VERSION = "005010X221A1"   # 835 version


def _seg(*elements: str) -> str:
    return _ELEM_SEP.join(str(e) for e in elements) + _SEG_TERM


def _money(value) -> str:
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return "0.00"


def _edi_date(iso_str: Optional[str] = None) -> str:
    """YYYYMMDD — falls back to today if missing."""
    if not iso_str:
        return datetime.now(timezone.utc).strftime("%Y%m%d")
    clean = iso_str.strip()[:10].replace("-", "")
    return clean


def _edi_time(iso_str: Optional[str] = None) -> str:
    """HHMM — falls back to current UTC time if missing."""
    if not iso_str:
        return datetime.now(timezone.utc).strftime("%H%M")
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%H%M")
    except Exception:
        return datetime.now(timezone.utc).strftime("%H%M")


def _alpha(s: Optional[str], max_len: int = 35) -> str:
    import re
    if not s:
        return "UNKNOWN"
    return re.sub(r"[^A-Za-z0-9 ]", "", s).strip().upper()[:max_len]


# ── Status code mapping ───────────────────────────────────────────────────────
# X12 CLM02 status codes for CLP segment
_CLM_STATUS: dict[str, str] = {
    "PAID":            "1",   # 1 = Processed as Primary
    "PARTIALLY_PAID":  "2",   # 2 = Processed as Secondary (closest analogue)
    "DENIED":          "4",   # 4 = Denied
    "APPEALED":        "4",   # Treat as denied for remittance purpose
}

# X12 CAS group codes
_CAS_GROUP = {
    "PAID":            "CO",  # CO = Contractual Obligation
    "PARTIALLY_PAID":  "CO",
    "DENIED":          "OA",  # OA = Other Adjustments
}

# ANSI claim adjustment reason codes (CARCs)
_CARC_CODE = {
    "PAID":            "45",   # 45 = Charge exceeds contracted/Medicare-approved amount
    "PARTIALLY_PAID":  "45",
    "DENIED":         "96",    # 96 = Non-covered charge(s)
}


def build_edi_835(
    *,
    claim_id: str,
    claim_status: str,
    total_billed: float,
    total_paid: float,
    org_name: str,
    payer_name: str,
    patient_name: Optional[str] = None,
    patient_dob: Optional[str] = None,
    service_date: Optional[str] = None,
    fhir_claim: Optional[dict] = None,
    denial_reason: Optional[str] = None,
) -> str:
    """
    Build a complete ANSI X12 835 EDI remittance advice string.

    Parameters
    ----------
    claim_id      UUID of the claim row
    claim_status  One of PAID, PARTIALLY_PAID, DENIED
    total_billed  Hospital's total billed amount
    total_paid    Amount the payer is paying (0.00 for DENIED)
    org_name      Hospital / provider name
    payer_name    Insurance payer name
    patient_name  Full name of the patient (optional)
    service_date  ISO date string for DTP payment date
    fhir_claim    FHIR claim proposal dict for line-level detail (optional)
    denial_reason Free-text reason (for DENIED claims, shown in CAS)
    """
    now = datetime.now(timezone.utc)
    isa_date = now.strftime("%y%m%d")
    isa_time = now.strftime("%H%M")
    gs_date = now.strftime("%Y%m%d")

    sender_id = _SENDER_ID
    receiver_id = _alpha(payer_name, 9) or "UNKNPAYER"
    org_name_edi = _alpha(org_name, 35)
    payer_name_edi = _alpha(payer_name, 35)
    patient_name_edi = _alpha(patient_name, 35) if patient_name else "UNKNOWN PATIENT"

    claim_control = claim_id.replace("-", "")[:20]
    interchange_ctrl = "000000002"
    group_ctrl = "2"
    txn_ctrl = "0001"
    payment_date = _edi_date(service_date)

    # Lookup mapping for claim status
    clm_status_code = _CLM_STATUS.get(claim_status, "4")
    cas_group = _CAS_GROUP.get(claim_status, "OA")
    carc_code = _CARC_CODE.get(claim_status, "96")

    total_adjustments = total_billed - total_paid

    segments: list[str] = []

    def add(*elements: str):
        segments.append(_seg(*elements))

    # ── ISA: Interchange Control Header ──────────────────────────────────────
    add(
        "ISA", "00", "          ", "00", "          ",
        "ZZ", f"{sender_id:<15}",
        "ZZ", f"{receiver_id:<15}",
        isa_date, isa_time,
        "^", "00501",
        f"{interchange_ctrl:>9}",
        "0", "T", _SUBELEMENT_SEP,
    )

    # ── GS: Functional Group Header ──────────────────────────────────────────
    add("GS", "HP", sender_id, receiver_id, gs_date, isa_time, group_ctrl, "X", _VERSION)

    # ── ST: Transaction Set Header (835) ─────────────────────────────────────
    add("ST", "835", txn_ctrl, _VERSION)

    # ── BPR: Beginning of Payment/Remittance ─────────────────────────────────
    # BPR01 = I (information only, no EFT) or C (check), BPR02 = total paid
    # For DENIED = 0.00, for PAID = total_paid
    add(
        "BPR",
        "I",                        # BPR01: I = info, C = check, A = ACH
        _money(total_paid),         # BPR02: total payment amount
        "C",                        # BPR03: C = credit
        "NON",                      # BPR04: NON = non-EFT
        "", "", "", "", "", "",      # BPR05-10: bank routing (not applicable)
        payment_date,               # BPR16: payment date
    )

    # ── TRN: Trace Number (claim UUID as trace) ───────────────────────────────
    add("TRN", "1", claim_control, "9" + sender_id)

    # ── REF: Payer reference ──────────────────────────────────────────────────
    add("REF", "EV", receiver_id[:9])

    # ── DTM: Payment Date ─────────────────────────────────────────────────────
    add("DTM", "405", payment_date)

    # ── 1000A: Payer Name Loop ────────────────────────────────────────────────
    add("N1", "PR", payer_name_edi)

    # ── 1000B: Provider (Hospital) Name Loop ─────────────────────────────────
    add("N1", "PE", org_name_edi, "XX", "1234567890")

    # ── 2100: Claim Payment Information ──────────────────────────────────────
    # CLP: Claim-Level Payment
    # CLP01 = submitter claim ID
    # CLP02 = claim status code
    # CLP03 = total billed
    # CLP04 = total paid
    # CLP05 = patient responsibility
    # CLP06 = claim type (11 = professional)
    # CLP07 = payer claim control number
    patient_responsibility = total_billed - total_paid
    add(
        "CLP",
        claim_control,              # CLP01: submitter claim ID
        clm_status_code,            # CLP02: 1=paid, 2=partial, 4=denied
        _money(total_billed),       # CLP03: total billed
        _money(total_paid),         # CLP04: total paid
        _money(max(patient_responsibility, 0.0)),  # CLP05: patient responsibility
        "11",                       # CLP06: 11 = Professional
        "INT" + claim_control[:10], # CLP07: payer internal claim number
    )

    # ── NM1*QC: Patient Name ──────────────────────────────────────────────────
    name_parts = patient_name_edi.split(" ") if patient_name else []
    last_name = name_parts[-1] if name_parts else "UNKNOWN"
    first_name = name_parts[0] if len(name_parts) > 1 else ""
    add("NM1", "QC", "1", last_name, first_name)

    # ── DTM*232: Service Date (claim level) ──────────────────────────────────
    add("DTM", "232", _edi_date(service_date))

    # ── CAS: Claim Adjustment ─────────────────────────────────────────────────
    # Only emit if there is an adjustment (write-off or denial)
    if abs(total_adjustments) > 0.001:
        # CAS01=group, CAS02=CARC, CAS03=adjustment amount
        cas_ref = f"DENIED – {denial_reason}" if denial_reason and claim_status == "DENIED" else ""
        add("CAS", cas_group, carc_code, _money(total_adjustments))

    # ── 2110: Service Payment Information (line level) ────────────────────────
    # Derive from fhir_claim.item[] when available
    fhir_items: list = (fhir_claim or {}).get("item") or []

    if fhir_items:
        for idx, item in enumerate(fhir_items, start=1):
            cpt_codings = (item.get("productOrService") or {}).get("coding") or []
            cpt_code = cpt_codings[0].get("code", "") if cpt_codings else ""
            if not cpt_code:
                continue

            unit_price = float((item.get("unitPrice") or {}).get("value") or 0.0)
            net_price = float((item.get("net") or {}).get("value") or unit_price)

            # Proportionate paid amount for each line (simple equal split)
            if total_billed > 0:
                line_paid = round(net_price * (total_paid / total_billed), 2)
            else:
                line_paid = 0.0

            line_adj = net_price - line_paid

            # SVC: Service line
            # SVC01 = HC:CPT_CODE  SVC02 = billed  SVC03 = paid
            add(
                "SVC",
                "HC" + _SUBELEMENT_SEP + cpt_code,
                _money(net_price),
                _money(line_paid),
            )
            add("DTM", "472", _edi_date(service_date))

            # Line-level adjustment
            if abs(line_adj) > 0.001:
                add("CAS", cas_group, carc_code, _money(line_adj))

    # ── SE: Transaction Set Trailer ───────────────────────────────────────────
    seg_count = len(segments) + 1  # +1 for SE itself
    add("SE", str(seg_count), txn_ctrl)

    # ── GE / IEA ─────────────────────────────────────────────────────────────
    add("GE", "1", group_ctrl)
    add("IEA", "1", f"{interchange_ctrl:>9}")

    return "\n".join(segments)
