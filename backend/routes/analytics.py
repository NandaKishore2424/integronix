"""
routes/analytics.py — Org-level Analytics API (Phase 6C)

  GET /analytics/overview   → KPI cards + 30-day trend data
  GET /analytics/top-codes  → Top AI codes by frequency
  GET /analytics/discrepancy-breakdown → Discrepancy type distribution

All aggregates are computed in Python over raw rows from coding_results.
No stored procedures needed — keeps the logic visible and testable.
"""
from fastapi import APIRouter, HTTPException
from collections import defaultdict, Counter
from datetime import datetime, timezone, timedelta
from database import select
from models import (
    AnalyticsOverview, TrendPoint, DiscrepancyBreakdown,
    TopCodeItem, AnalyticsTopCodes,
)
from logger import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/analytics", tags=["Analytics"])


# ── GET /analytics/overview ────────────────────────────────────────────────────

@router.get(
    "/overview",
    response_model=AnalyticsOverview,
    summary="KPI cards + 30-day daily case trend",
)
async def get_analytics_overview():
    """
    Returns:
      - KPI cards: total cases, revenue recovered, avg confidence, high-risk rate
      - 30-day trend: daily case count + daily revenue delta
      - Risk distribution: {LOW: n, MEDIUM: n, HIGH: n}
      - Source breakdown: {text_input: n, pdf_upload: n}
    """
    try:
        # Fetch coding_results joined with clinical_cases for document_source
        rows = await select(
            "coding_results",
            query=(
                "risk_label,discrepancy_type,financial_delta,"
                "confidence_score,created_at,"
                "clinical_cases(document_source)"
            ),
        )
    except Exception as e:
        log.error("analytics_overview_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Analytics query failed: {str(e)}")

    now    = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=30)

    total_cases     = len(rows)
    revenue_sum     = 0.0
    confidence_sum  = 0.0
    high_risk_count = 0
    risk_dist       = {"LOW": 0, "MEDIUM": 0, "HIGH": 0}
    source_dist     = {"text_input": 0, "pdf_upload": 0}

    # Daily buckets for the 30-day trend
    daily_cases:   dict[str, int]   = defaultdict(int)
    daily_revenue: dict[str, float] = defaultdict(float)

    for r in rows:
        label = r.get("risk_label", "LOW")
        delta = float(r.get("financial_delta") or 0)
        conf  = float(r.get("confidence_score") or 0)
        cc    = r.get("clinical_cases") or {}
        src   = cc.get("document_source", "text_input") if isinstance(cc, dict) else "text_input"

        # KPI accumulators
        if label in risk_dist:
            risk_dist[label] += 1
        if label == "HIGH":
            high_risk_count += 1
        if delta > 0:
            revenue_sum += delta
        confidence_sum += conf

        # Source breakdown
        if src in source_dist:
            source_dist[src] += 1

        # Trend — only last 30 days
        created_str = r.get("created_at", "")
        try:
            # Handle both Z and +00:00 formats
            created = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
            if created >= cutoff:
                day_key = created.strftime("%Y-%m-%d")
                daily_cases[day_key]   += 1
                daily_revenue[day_key] += delta
        except Exception:
            pass

    avg_confidence = round((confidence_sum / total_cases * 100) if total_cases > 0 else 0.0, 1)
    high_risk_rate = round((high_risk_count / total_cases * 100) if total_cases > 0 else 0.0, 1)

    # Build 30-day trend list (include all 30 days even if 0)
    trend: list[TrendPoint] = []
    for i in range(29, -1, -1):
        day = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        trend.append(TrendPoint(
            date=day,
            cases=daily_cases.get(day, 0),
            revenue=round(daily_revenue.get(day, 0.0), 2),
        ))

    return AnalyticsOverview(
        total_cases=total_cases,
        total_revenue_recovered=round(revenue_sum, 2),
        avg_confidence=avg_confidence,
        high_risk_rate=high_risk_rate,
        risk_distribution=risk_dist,
        source_distribution=source_dist,
        trend=trend,
    )


# ── GET /analytics/top-codes ───────────────────────────────────────────────────

@router.get(
    "/top-codes",
    response_model=AnalyticsTopCodes,
    summary="Top 10 AI-assigned ICD codes by frequency",
)
async def get_top_codes():
    """
    Counts how many times each ai_icd_code has been assigned.
    Returns top 10 with avg revenue delta and avg risk score.
    Useful for spotting frequently-missed or over-used codes.
    """
    try:
        rows = await select(
            "coding_results",
            query="ai_icd_code,financial_delta,risk_score,risk_label,discrepancy_type",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Top codes query failed: {str(e)}")

    # Aggregate per code
    code_data: dict[str, dict] = defaultdict(lambda: {
        "count": 0, "revenue": 0.0, "risk_sum": 0.0, "discrepancies": []
    })
    for r in rows:
        code = r.get("ai_icd_code") or "UNKNOWN"
        code_data[code]["count"]       += 1
        code_data[code]["revenue"]     += float(r.get("financial_delta") or 0)
        code_data[code]["risk_sum"]    += float(r.get("risk_score") or 0)
        code_data[code]["discrepancies"].append(r.get("discrepancy_type", "NO_COMPARISON"))

    # Sort by count desc, take top 10
    top = sorted(code_data.items(), key=lambda x: x[1]["count"], reverse=True)[:10]

    items: list[TopCodeItem] = []
    for code, d in top:
        cnt = d["count"]
        # Most common discrepancy for this code
        disc_counter = Counter(d["discrepancies"])
        most_common  = disc_counter.most_common(1)[0][0] if disc_counter else "NO_COMPARISON"
        items.append(TopCodeItem(
            code=code,
            count=cnt,
            avg_revenue=round(d["revenue"] / cnt, 2),
            avg_risk=round(d["risk_sum"] / cnt, 4),
            top_discrepancy=most_common,
        ))

    return AnalyticsTopCodes(codes=items)


# ── GET /analytics/discrepancy-breakdown ──────────────────────────────────────

@router.get(
    "/discrepancy-breakdown",
    summary="Count of each discrepancy type (for pie / donut chart)",
)
async def get_discrepancy_breakdown():
    """
    Returns count per discrepancy_type for the doughnut chart.
    """
    try:
        rows = await select("coding_results", query="discrepancy_type")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Discrepancy query failed: {str(e)}")

    counter: Counter = Counter()
    for r in rows:
        dt = r.get("discrepancy_type") or "NO_COMPARISON"
        counter[dt] += 1

    LABELS = {
        "EXACT_MATCH":             "✓ Exact Match",
        "NO_COMPARISON":           "— No Comparison",
        "SPECIFICITY_IMPROVEMENT": "↑ Specificity",
        "CODE_DIVERGENCE":         "⚠ Diverged",
        "OVERCODING":              "⬆ Overcode",
        "UNSUPPORTED_CODE":        "✗ Unsupported",
    }

    return [
        {"type": k, "label": LABELS.get(k, k), "count": v}
        for k, v in counter.most_common()
    ]
