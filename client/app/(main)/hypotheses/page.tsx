"use client";

import { useEffect, useState } from "react";

const API = "/api";

interface Hypothesis {
  id: number;
  question: string;
  status: string;
  priority: number;
  category: string;
  confidence: number | null;
  test_result: string | null;
  evidence: Record<string, unknown> | null;
  created_at: string | null;
  tested_at: string | null;
}

const statusBadge: Record<string, string> = {
  generated: "badge-blue",
  tested: "badge-yellow",
  error: "badge-red",
};

export default function HypothesesPage() {
  const [hypotheses, setHypotheses] = useState<Hypothesis[]>([]);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [categoryFilter, setCategoryFilter] = useState<string>("");

  useEffect(() => {
    const params = new URLSearchParams();
    if (statusFilter) params.set("status", statusFilter);
    if (categoryFilter) params.set("category", categoryFilter);
    params.set("limit", "500");
    fetch(`${API}/research/hypotheses?${params}`).then((r) => r.json()).then((d) => {
      setHypotheses(d.hypotheses ?? []);
    });
  }, [statusFilter, categoryFilter]);

  const categories = [...new Set(hypotheses.map((h) => h.category))];

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-bold text-white">Hypothesis Lab</h1>

      <div className="flex gap-3 flex-wrap">
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="bg-[#1e293b] border border-[#334155] rounded px-2 py-1 text-white text-sm"
        >
          <option value="">All Statuses</option>
          <option value="generated">Generated</option>
          <option value="tested">Tested</option>
          <option value="error">Error</option>
        </select>
        <select
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
          className="bg-[#1e293b] border border-[#334155] rounded px-2 py-1 text-white text-sm"
        >
          <option value="">All Categories</option>
          {categories.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        <span className="text-sm text-[#64748b] self-center">{hypotheses.length} hypotheses</span>
      </div>

      <div className="card flex flex-col gap-2">
        {hypotheses.length === 0 && <p className="text-sm text-[#64748b]">No hypotheses match filters</p>}
        {hypotheses.map((h) => (
          <div key={h.id} className="border-b border-[#1e293b] last:border-0 py-3">
            <div className="flex items-start gap-3">
              <span className={`badge ${statusBadge[h.status] ?? "badge-gray"} shrink-0 mt-0.5`}>
                {h.status}
              </span>
              <div className="min-w-0 flex-1">
                <div className="text-white text-sm">{h.question}</div>
                <div className="flex gap-3 mt-1 text-xs text-[#64748b]">
                  <span>Priority: {h.priority}</span>
                  <span>Category: {h.category}</span>
                  {h.confidence != null && <span>Confidence: {h.confidence.toFixed(2)}</span>}
                  {h.test_result && (
                    <span className={h.test_result === "supported" ? "text-[#6ee7b7]" : "text-[#fca5a5]"}>
                      {h.test_result}
                    </span>
                  )}
                </div>
                {h.evidence && (
                  <pre className="mt-1 text-xs text-[#475569] overflow-x-auto max-h-20">
                    {JSON.stringify(h.evidence, null, 2).slice(0, 300)}
                  </pre>
                )}
              </div>
              {h.created_at && (
                <div className="text-[#475569] text-xs shrink-0">
                  {new Date(h.created_at).toLocaleDateString()}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
