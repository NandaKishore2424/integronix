"use client";

import { CaseSummary } from "@/types/cases";
import { useEffect, useState } from "react";
import { fetchCases } from "@/lib/api";

export default function CasesPage() {
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadCases() {
      try {
        const data = await fetchCases();
        setCases(data.cases || []); // Corrected property name to match CaseListResponse
      } catch (err) {
        setError("Failed to load cases.");
      } finally {
        setLoading(false);
      }
    }

    loadCases();
  }, []);

  if (loading) {
    return <div>Loading...</div>;
  }

  if (error) {
    return <div className="text-red-500">{error}</div>;
  }

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-4">Case History</h1>
      <ul className="space-y-4">
        {cases.map((c: CaseSummary) => (
          <li key={c.result_id} className="p-4 border rounded-lg">
            <h2 className="text-lg font-semibold">Case ID: {c.result_id}</h2>
            <p>Risk Label: {c.risk_label}</p>
            <p>Document Source: {c.document_source}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}