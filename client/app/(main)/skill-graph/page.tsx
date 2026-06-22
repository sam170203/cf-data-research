"use client";

import { useEffect, useState } from "react";

const API = "/api";

interface Edge {
  source: string;
  target: string;
  count: number;
  users: number;
  avg_rating_gain: number;
  avg_source_rating: number | null;
  avg_target_rating: number | null;
}

interface SkillGraph {
  edges: Edge[];
  nodes: string[];
  high_gain_transitions: Edge[];
  expert_trajectories: Edge[];
}

export default function SkillGraphPage() {
  const [data, setData] = useState<SkillGraph | null>(null);
  const [minUsers, setMinUsers] = useState(2);

  useEffect(() => {
    fetch(`${API}/research/skill-graph?min_users=${minUsers}&limit=100`).then((r) => r.json()).then(setData);
  }, [minUsers]);

  const topEdges = (data?.edges ?? []).slice(0, 15);

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-bold text-white">Skill Graph</h1>

      <div className="flex items-center gap-3">
        <label className="text-sm text-[#94a3b8]">Min users per edge:</label>
        <select
          value={minUsers}
          onChange={(e) => setMinUsers(Number(e.target.value))}
          className="bg-[#1e293b] border border-[#334155] rounded px-2 py-1 text-white text-sm"
        >
          <option value={1}>1</option>
          <option value={2}>2</option>
          <option value={3}>3</option>
          <option value={5}>5</option>
        </select>
        <span className="text-xs text-[#64748b]">
          {data?.nodes.length ?? 0} tags, {data?.edges.length ?? 0} transitions
        </span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Top Transitions Table */}
        <div>
          <h2 className="text-lg font-semibold text-white mb-3">Top Tag Transitions</h2>
          <div className="card overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[#94a3b8] border-b border-[#334155]">
                  <th className="text-left py-2 pr-4">From</th>
                  <th className="text-left py-2 pr-4">To</th>
                  <th className="text-right py-2 pr-4">Count</th>
                  <th className="text-right py-2">Users</th>
                </tr>
              </thead>
              <tbody>
                {topEdges.map((e, i) => (
                  <tr key={i} className="border-b border-[#1e293b] last:border-0">
                    <td className="py-2 pr-4 text-white">{e.source}</td>
                    <td className="py-2 pr-4 text-[#94a3b8]">→ {e.target}</td>
                    <td className="py-2 pr-4 text-right text-white">{e.count}</td>
                    <td className="py-2 text-right text-[#94a3b8]">{e.users}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* High Gain Transitions */}
        <div>
          <h2 className="text-lg font-semibold text-white mb-3">
            Highest Rating-Gain Transitions
          </h2>
          <div className="card overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[#94a3b8] border-b border-[#334155]">
                  <th className="text-left py-2 pr-4">From</th>
                  <th className="text-left py-2 pr-4">To</th>
                  <th className="text-right py-2 pr-4">Avg Gain</th>
                  <th className="text-right py-2">Users</th>
                </tr>
              </thead>
              <tbody>
                {(data?.high_gain_transitions ?? []).length === 0 && (
                  <tr><td colSpan={4} className="py-4 text-center text-[#64748b] text-sm">No high-gain transitions found</td></tr>
                )}
                {(data?.high_gain_transitions ?? []).map((e, i) => (
                  <tr key={i} className="border-b border-[#1e293b] last:border-0">
                    <td className="py-2 pr-4 text-white">{e.source}</td>
                    <td className="py-2 pr-4 text-[#94a3b8]">→ {e.target}</td>
                    <td className="py-2 pr-4 text-right text-[#34d399]">+{e.avg_rating_gain.toFixed(0)}</td>
                    <td className="py-2 text-right text-[#94a3b8]">{e.users}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Expert Trajectories */}
      <div>
        <h2 className="text-lg font-semibold text-white mb-3">
          Expert Trajectories (crossing 1600)
        </h2>
        <div className="card overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[#94a3b8] border-b border-[#334155]">
                <th className="text-left py-2 pr-4">From Tag</th>
                <th className="text-left py-2 pr-4">To Tag</th>
                <th className="text-right py-2 pr-4">Src Rating</th>
                <th className="text-right py-2 pr-4">Tgt Rating</th>
                <th className="text-right py-2">Users</th>
              </tr>
            </thead>
            <tbody>
              {(data?.expert_trajectories ?? []).length === 0 && (
                <tr><td colSpan={5} className="py-4 text-center text-[#64748b] text-sm">No expert trajectories found</td></tr>
              )}
              {(data?.expert_trajectories ?? []).map((e, i) => (
                <tr key={i} className="border-b border-[#1e293b] last:border-0">
                  <td className="py-2 pr-4 text-white">{e.source}</td>
                  <td className="py-2 pr-4 text-[#94a3b8]">→ {e.target}</td>
                  <td className="py-2 pr-4 text-right text-[#fbbf24]">{e.avg_source_rating?.toFixed(0)}</td>
                  <td className="py-2 pr-4 text-right text-[#34d399]">{e.avg_target_rating?.toFixed(0)}</td>
                  <td className="py-2 text-right text-[#94a3b8]">{e.users}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
