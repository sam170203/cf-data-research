"use client";

import { useEffect, useState } from "react";

const API = "/api";

interface MilestoneUser {
  user_id: number;
  handle: string;
  achieved_at_rating: number;
  days_to_achieve: number | null;
  contests_to_achieve: number | null;
  start_rating: number;
  first_6mo: Record<string, number> | null;
  pre_breakthrough_6mo: Record<string, number> | null;
}

interface MilestoneSummary {
  total_users: number;
  avg_days: number | null;
  avg_contests: number | null;
  avg_start_rating: number;
}

export default function TrajectoriesPage() {
  const [milestones, setMilestones] = useState<Record<string, MilestoneUser[]>>({});
  const [summary, setSummary] = useState<Record<string, MilestoneSummary>>({});
  const [selected, setSelected] = useState<string>("expert");

  useEffect(() => {
    fetch(`${API}/research/trajectories?limit=500`).then((r) => r.json()).then((d) => {
      setMilestones(d.milestones ?? {});
      setSummary(d.summary ?? {});
    });
  }, []);

  const milestoneLabels: Record<string, string> = {
    expert: "Expert (1600)",
    candidate_master: "Candidate Master (1900)",
    master: "Master (2100)",
    gain_300: "+300 Rating Gain",
    gain_500: "+500 Rating Gain",
    breakthrough: "100+ Breakthrough",
  };

  const currentUsers = milestones[selected] ?? [];
  const currentSummary = summary[selected];

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-bold text-white">Expert Journey Dashboard</h1>
      <p className="text-sm text-[#94a3b8]">
        Understand the paths users take to reach rating milestones.
      </p>

      {/* Milestone Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
        {Object.entries(summary).map(([key, s]) => (
          <div key={key} className="card">
            <div className="stat-label">{milestoneLabels[key] ?? key}</div>
            <div className="stat-value text-[#60a5fa] text-lg">{s.total_users}</div>
            <div className="text-xs text-[#64748b] mt-1">
              {s.avg_days != null ? `${s.avg_days}d avg` : "—"} · {s.avg_contests != null ? `${s.avg_contests} contests` : "—"}
            </div>
          </div>
        ))}
      </div>

      {/* Selector */}
      <div className="flex items-center gap-3">
        <label className="text-sm text-[#94a3b8]">Milestone:</label>
        <select
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
          className="bg-[#1e293b] border border-[#334155] rounded px-2 py-1 text-white text-sm"
        >
          {Object.keys(milestones).map((k) => (
            <option key={k} value={k}>{milestoneLabels[k] ?? k} ({milestones[k].length})</option>
          ))}
        </select>
        {currentSummary && (
          <span className="text-xs text-[#64748b]">
            Avg: {currentSummary.avg_days ?? "?"}d · {currentSummary.avg_contests ?? "?"} contests · Start: {currentSummary.avg_start_rating.toFixed(0)}
          </span>
        )}
      </div>

      {/* Users Table */}
      <div className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-[#94a3b8] border-b border-[#334155]">
              <th className="text-left py-2 pr-4">Handle</th>
              <th className="text-right py-2 pr-4">Start Rating</th>
              <th className="text-right py-2 pr-4">Achieved At</th>
              <th className="text-right py-2 pr-4">Days</th>
              <th className="text-right py-2 pr-4">Contests</th>
              <th className="text-right py-2 pr-4">First 6mo Gain</th>
              <th className="text-right py-2 pr-4">First 6mo Contests</th>
              <th className="text-right py-2">Pre-BT Gain</th>
            </tr>
          </thead>
          <tbody>
            {currentUsers.map((u) => (
              <tr key={u.user_id} className="border-b border-[#1e293b] last:border-0">
                <td className="py-2 pr-4 text-white font-medium">{u.handle}</td>
                <td className="py-2 pr-4 text-right text-[#94a3b8]">{u.start_rating}</td>
                <td className="py-2 pr-4 text-right text-[#34d399]">{u.achieved_at_rating}</td>
                <td className="py-2 pr-4 text-right">{u.days_to_achieve ?? "—"}</td>
                <td className="py-2 pr-4 text-right">{u.contests_to_achieve ?? "—"}</td>
                <td className="py-2 pr-4 text-right">
                  {u.first_6mo ? (
                    <span className={u.first_6mo.total_gain >= 0 ? "text-[#34d399]" : "text-[#fca5a5]"}>
                      {u.first_6mo.total_gain > 0 ? "+" : ""}{u.first_6mo.total_gain}
                    </span>
                  ) : "—"}
                </td>
                <td className="py-2 pr-4 text-right">{u.first_6mo?.n_contests ?? "—"}</td>
                <td className="py-2 text-right">
                  {u.pre_breakthrough_6mo ? (
                    <span className={u.pre_breakthrough_6mo.total_gain >= 0 ? "text-[#34d399]" : "text-[#fca5a5]"}>
                      {u.pre_breakthrough_6mo.total_gain > 0 ? "+" : ""}{u.pre_breakthrough_6mo.total_gain}
                    </span>
                  ) : "—"}
                </td>
              </tr>
            ))}
            {currentUsers.length === 0 && (
              <tr><td colSpan={8} className="py-8 text-center text-[#64748b] text-sm">No data yet</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Pattern Summary */}
      {currentSummary && currentUsers.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="card">
            <div className="stat-label">Avg Days to Milestone</div>
            <div className="stat-value text-[#60a5fa]">{currentSummary.avg_days ?? "—"}</div>
          </div>
          <div className="card">
            <div className="stat-label">Avg Contests to Milestone</div>
            <div className="stat-value text-[#34d399]">{currentSummary.avg_contests ?? "—"}</div>
          </div>
          <div className="card">
            <div className="stat-label">Avg Start Rating</div>
            <div className="stat-value text-[#a78bfa]">{currentSummary.avg_start_rating.toFixed(0)}</div>
          </div>
        </div>
      )}
    </div>
  );
}
