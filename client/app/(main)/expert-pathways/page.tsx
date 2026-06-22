"use client";

import { useEffect, useState } from "react";

const API = "/api";

interface TagFreq {
  [tag: string]: number;
}

interface Transition {
  path: string;
  count: number;
  frequency: number;
}

interface CommonPath {
  path: string[];
  count: number;
  frequency: number;
}

interface TransitionGraph {
  from: string;
  to: [string, number][];
  total: number;
}

interface MilestonePathways {
  milestone: number;
  name: string;
  total_users: number;
  total_with_tags: number;
  common_first_tags: { tag: string; count: number; frequency: number }[];
  most_common_transitions: Transition[];
  most_common_paths: CommonPath[];
  transition_graph: TransitionGraph[];
  avg_adoption_order: TagFreq;
}

type PathwaysData = Record<string, MilestonePathways>;

const MILESTONE_COLORS: Record<string, string> = {
  specialist: "#60a5fa",
  expert: "#34d399",
  candidate_master: "#fbbf24",
  master: "#f472b6",
  grandmaster: "#a78bfa",
};

export default function ExpertPathwaysPage() {
  const [data, setData] = useState<PathwaysData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string>("expert");

  useEffect(() => {
    fetch(`${API}/research/expert-pathways`, { signal: AbortSignal.timeout(300000) })
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then(setData)
      .catch((e) => setError(e.message));
  }, []);

  if (!data) {
    return (
      <div className="flex flex-col gap-6 items-center justify-center py-12">
        <div className="text-4xl mb-4">🧠</div>
        <h1 className="text-2xl font-bold text-white">Computing Expert Pathways...</h1>
        <p className="text-sm text-[#94a3b8] text-center max-w-md">
          This analyzes tag progression for all {325} users across 5 rating milestones.
          It takes about a minute on the first load.
        </p>
        <div className="w-8 h-8 border-2 border-[#60a5fa] border-t-transparent rounded-full animate-spin mt-4" />
        {error && <p className="text-sm text-[#fca5a5] mt-4">Error: {error}</p>}
      </div>
    );
  }

  const ms = data[selected];

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-bold text-white">Expert Pathways</h1>
      <p className="text-sm text-[#94a3b8]">
        Most common tag progression paths to each rating milestone.
      </p>

      {/* Milestone selector */}
      <div className="flex gap-2 flex-wrap">
        {Object.entries(data).map(([key, m]) => (
          <button
            key={key}
            onClick={() => setSelected(key)}
            className={`px-4 py-2 rounded text-sm font-medium ${
              selected === key
                ? "text-white"
                : "bg-[#1e293b] text-[#94a3b8]"
            }`}
            style={selected === key ? { backgroundColor: MILESTONE_COLORS[key] ?? "#60a5fa" } : {}}
          >
            {m.name} ({m.total_users})
          </button>
        ))}
      </div>

      {/* Overview */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="card">
          <div className="stat-label">Users Reached</div>
          <div className="stat-value text-[#60a5fa]">{ms.total_users}</div>
        </div>
        <div className="card">
          <div className="stat-label">With Tag Data</div>
          <div className="stat-value text-[#34d399]">{ms.total_with_tags}</div>
        </div>
        <div className="card">
          <div className="stat-label">Unique First Tags</div>
          <div className="stat-value text-[#fbbf24]">{ms.common_first_tags.length}</div>
        </div>
        <div className="card">
          <div className="stat-label">Unique Transitions</div>
          <div className="stat-value text-[#a78bfa]">{ms.most_common_transitions.length}</div>
        </div>
      </div>

      {/* Common first tags */}
      <div>
        <h2 className="text-lg font-semibold text-white mb-3">Most Common Starting Tags</h2>
        <div className="card overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[#94a3b8] border-b border-[#334155]">
                <th className="text-left py-2 pr-4">Tag</th>
                <th className="text-right py-2 pr-4">Users</th>
                <th className="text-right py-2">Frequency</th>
              </tr>
            </thead>
            <tbody>
              {ms.common_first_tags.slice(0, 15).map((t, i) => (
                <tr key={i} className="border-b border-[#1e293b] last:border-0">
                  <td className="py-2 pr-4 text-white">{t.tag}</td>
                  <td className="py-2 pr-4 text-right text-[#94a3b8]">{t.count}</td>
                  <td className="py-2 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <div className="w-20 h-2 bg-[#1e293b] rounded-full overflow-hidden">
                        <div className="h-full bg-[#60a5fa] rounded-full" style={{ width: `${t.frequency * 100}%` }} />
                      </div>
                      <span className="text-[#94a3b8] w-12 text-right">{(t.frequency * 100).toFixed(1)}%</span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Top transitions */}
      <div>
        <h2 className="text-lg font-semibold text-white mb-3">Most Common Tag Transitions</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {ms.most_common_transitions.slice(0, 20).map((t, i) => (
            <div key={i} className="card text-sm">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-white">{t.path.split(" → ")[0]}</span>
                <span className="text-[#64748b]">→</span>
                <span className="text-[#34d399]">{t.path.split(" → ")[1]}</span>
              </div>
              <div className="text-xs text-[#94a3b8]">
                {t.count} users ({(t.frequency * 100).toFixed(1)}%)
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Top 3-tag paths */}
      {ms.most_common_paths.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold text-white mb-3">Most Common 3-Step Paths</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {ms.most_common_paths.slice(0, 12).map((p, i) => (
              <div key={i} className="card text-sm">
                <div className="flex items-center gap-1.5 mb-1 flex-wrap">
                  {p.path.map((tag, j) => (
                    <span key={j} className="flex items-center gap-1">
                      <span className="text-white">{tag}</span>
                      {j < p.path.length - 1 && <span className="text-[#64748b]">→</span>}
                    </span>
                  ))}
                </div>
                <div className="text-xs text-[#94a3b8]">
                  {p.count} users ({(p.frequency * 100).toFixed(1)}%)
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Transition graph (top connections) */}
      {ms.transition_graph.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold text-white mb-3">Transition Graph (Top Sources)</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {ms.transition_graph.slice(0, 12).map((node, i) => (
              <div key={i} className="card text-sm">
                <div className="text-white font-medium mb-2">{node.from}</div>
                <div className="space-y-1">
                  {node.to.slice(0, 5).map(([tag, count], j) => (
                    <div key={j} className="flex items-center justify-between text-xs">
                      <span className="text-[#94a3b8]">→ {tag}</span>
                      <span className="text-[#64748b]">{count} ({(count / node.total * 100).toFixed(0)}%)</span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Adoption order */}
      {Object.keys(ms.avg_adoption_order).length > 0 && (
        <div>
          <h2 className="text-lg font-semibold text-white mb-3">Avg Tag Adoption Order</h2>
          <div className="card overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[#94a3b8] border-b border-[#334155]">
                  <th className="text-left py-2 pr-4">Tag</th>
                  <th className="text-right py-2">Avg Rank</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(ms.avg_adoption_order).map(([tag, rank], i) => (
                  <tr key={i} className="border-b border-[#1e293b] last:border-0">
                    <td className="py-2 pr-4 text-white">{tag}</td>
                    <td className="py-2 text-right text-[#94a3b8]">{rank}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
