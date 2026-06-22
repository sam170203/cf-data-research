"use client";

import { useEffect, useState } from "react";

const API = "/api";

interface TopEvent {
  user_id: number;
  handle: string;
  from_rating: number;
  to_rating: number;
  gain: number;
  days?: number;
}

interface BreakthroughDetail {
  key: string;
  description: string;
  total_events: number;
  avg_gain?: number;
  top_events?: TopEvent[];
  pre_breakthrough_pattern?: {
    avg_difficulty?: number;
    avg_solve_rate?: number;
    avg_solved?: number;
    avg_submissions?: number;
    dominant_tags?: string[];
  };
  strongest_predictors?: string[];
}

interface BreakthroughPlateauData {
  breakthrough_150_90d: BreakthroughDetail;
  breakthrough_300_180d: BreakthroughDetail;
  breakthrough_500_overall: BreakthroughDetail;
}

export default function BreakthroughsPage() {
  const [data, setData] = useState<BreakthroughPlateauData | null>(null);
  const [tab, setTab] = useState<string>("breakthrough_150_90d");

  useEffect(() => {
    fetch(`${API}/research/breakthrough-plateau`).then((r) => r.json()).then(setData);
  }, []);

  if (!data) {
    return (
      <div className="flex flex-col gap-6">
        <h1 className="text-2xl font-bold text-white">Breakthrough Dashboard</h1>
        <p className="text-sm text-[#94a3b8]">Loading...</p>
      </div>
    );
  }

  const bt = data[tab as keyof BreakthroughPlateauData] as BreakthroughDetail;
  const tabs = [
    { key: "breakthrough_150_90d", label: "+150 in 90d" },
    { key: "breakthrough_300_180d", label: "+300 in 180d" },
    { key: "breakthrough_500_overall", label: "+500 Overall" },
  ];

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-bold text-white">Breakthrough Dashboard</h1>
      <p className="text-sm text-[#94a3b8]">
        Patterns and top events before rapid rating gains.
      </p>

      {/* Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        {tabs.map((t) => {
          const d = data[t.key as keyof BreakthroughPlateauData] as BreakthroughDetail;
          return (
            <div key={t.key} className="card cursor-pointer" onClick={() => setTab(t.key)}>
              <div className="stat-label">{t.label}</div>
              <div className="stat-value text-[#60a5fa]">{d.total_events}</div>
              <div className="text-xs text-[#94a3b8]">avg +{d.avg_gain}</div>
            </div>
          );
        })}
      </div>

      {/* Tab content */}
      <div className="card">
        <div className="flex gap-2 mb-4 border-b border-[#334155] pb-2">
          {tabs.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`px-3 py-1 text-xs rounded ${tab === t.key ? "bg-[#60a5fa] text-white" : "bg-[#1e293b] text-[#94a3b8]"}`}
            >
              {t.label}
            </button>
          ))}
        </div>

        <h3 className="text-sm font-semibold text-white mb-2">{bt.description}</h3>
        <p className="text-xs text-[#94a3b8] mb-3">{bt.total_events} total events</p>

        {bt.pre_breakthrough_pattern && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
            <div>
              <div className="text-xs text-[#64748b]">Avg Difficulty</div>
              <div className="text-sm text-white">{bt.pre_breakthrough_pattern.avg_difficulty ?? "—"}</div>
            </div>
            <div>
              <div className="text-xs text-[#64748b]">Solve Rate</div>
              <div className="text-sm text-white">{bt.pre_breakthrough_pattern.avg_solve_rate ?? "—"}</div>
            </div>
            <div>
              <div className="text-xs text-[#64748b]">Avg Solved</div>
              <div className="text-sm text-white">{bt.pre_breakthrough_pattern.avg_solved ?? "—"}</div>
            </div>
            <div>
              <div className="text-xs text-[#64748b]">Avg Submissions</div>
              <div className="text-sm text-white">{bt.pre_breakthrough_pattern.avg_submissions ?? "—"}</div>
            </div>
          </div>
        )}

        {bt.pre_breakthrough_pattern?.dominant_tags && (
          <div className="mb-4">
            <div className="text-xs text-[#64748b] mb-1">Dominant pre-breakthrough tags:</div>
            <div className="flex flex-wrap gap-1">
              {bt.pre_breakthrough_pattern.dominant_tags.map((tag: string) => (
                <span key={tag} className="px-2 py-0.5 bg-[#1e293b] rounded text-xs text-[#fbbf24]">{tag}</span>
              ))}
            </div>
          </div>
        )}

        {bt.strongest_predictors && (
          <div className="mb-4">
            <div className="text-xs text-[#64748b] mb-1">Strongest predictors:</div>
            <div className="flex flex-wrap gap-1">
              {bt.strongest_predictors.map((tag: string) => (
                <span key={tag} className="px-2 py-0.5 bg-[#1e293b] rounded text-xs text-[#34d399]">{tag}</span>
              ))}
            </div>
          </div>
        )}

        {bt.top_events && bt.top_events.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[#94a3b8] border-b border-[#334155]">
                  <th className="text-left py-2 pr-4">Handle</th>
                  <th className="text-right py-2 pr-4">From</th>
                  <th className="text-right py-2 pr-4">To</th>
                  <th className="text-right py-2">Gain</th>
                </tr>
              </thead>
              <tbody>
                {bt.top_events.map((e, i) => (
                  <tr key={i} className="border-b border-[#1e293b] last:border-0">
                    <td className="py-2 pr-4 text-white font-medium">{e.handle}</td>
                    <td className="py-2 pr-4 text-right text-[#94a3b8]">{e.from_rating}</td>
                    <td className="py-2 pr-4 text-right text-[#34d399]">{e.to_rating}</td>
                    <td className="py-2 text-right text-[#fbbf24] font-bold">+{e.gain}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
