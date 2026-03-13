"use client";

import { useEffect, useState } from "react";
import { ApiError, getAnalyticsOverview, getTopCodes } from "@/lib/api";
import CandidateChart from "@/components/CandidateChart";
import AuditCard from "@/components/AuditCard";
import { IcdCandidate, Discrepancy } from "@/types/coding";
import { AnalyticsOverview } from "@/types/analytics";

export default function DashboardPage() {
  const [overview, setOverview] = useState<AnalyticsOverview | null>(null);
  const [topCodes, setTopCodes] = useState<IcdCandidate[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchData() {
      try {
        const analyticsOverview = await getAnalyticsOverview();
        const topICDCodes = await getTopCodes();
        setOverview(analyticsOverview);
        setTopCodes(topICDCodes.codes.map((code) => ({
          code: code.code,
          description: "",
          is_billable: false,
          is_cc: false,
          is_mcc: false,
          base_reimbursement: 0,
          icd_version: "",
          mapping_type: "",
          confidence: 0,
          is_primary: false,
          source: "",
          final_score: 0,
        })));
      } catch (err) {
        if (err instanceof ApiError) {
          setError(err.message);
        } else {
          setError("An unexpected error occurred.");
        }
      }
    }

    fetchData();
  }, []);

  if (error) {
    return <div className="text-red-500">Error: {error}</div>;
  }

  if (!overview) {
    return <div>Loading...</div>;
  }

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-4">Dashboard</h1>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <AuditCard
          discrepancy={{
            type: "EXACT_MATCH",
            ai_code: "",
            human_code: "",
            ai_description: "",
            human_description: "",
            explanation: "",
            revenue_delta: 0,
            drg_flag: null,
            ai_is_mcc: false,
            ai_is_cc: false,
          }}
          financialDelta={overview?.total_revenue_recovered || 0}
          drgFlag={null}
        />
      </div>

      {/* Top ICD Codes Chart */}
      <div className="mb-6">
        <h2 className="text-xl font-semibold mb-2">Top ICD Codes</h2>
        <CandidateChart candidates={topCodes} />
      </div>
    </div>
  );
}
