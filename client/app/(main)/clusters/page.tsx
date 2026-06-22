"use client";

import { useEffect, useState } from "react";

const API = "/api";

interface ClusterInfo {
  label: number;
  name: string;
  n_users: number;
  avg_rating: number;
  avg_max_rating: number;
  avg_growth_velocity: number;
  avg_growth_acceleration: number;
  avg_contests: number;
  avg_solved: number;
  avg_tag_diversity: number;
  avg_volatility: number;
  avg_submissions_per_day: number;
  avg_inactivity_streak: number;
  dominant_tags: Record<string, number>;
  handles: string[];
}

interface ClusterRun {
  id: number;
  run_id: string;
  algorithm: string;
  n_clusters: number;
  metric_value: number;
  clusters: { clusters: ClusterInfo[] };
  computed_at: string;
}

export default function ClustersPage() {
  const [runs, setRuns] = useState<ClusterRun[]>([]);
  const [selectedRun, setSelectedRun] = useState<number>(0);
  const [embeddings, setEmbeddings] = useState<{ user_id: number; handle: string; current_rating: number; cluster_label: number; cluster_name: string }[]>([]);

  useEffect(() => {
    fetch(`${API}/research/clusters?limit=10`).then((r) => r.json()).then((d) => {
      setRuns(d.runs ?? []);
    });
    fetch(`${API}/research/embeddings?limit=500`).then((r) => r.json()).then((d) => {
      setEmbeddings(d.users ?? []);
    });
  }, []);

  const current = runs[selectedRun];
  const clusters = current?.clusters?.clusters ?? [];
  const byCluster: Record<number, typeof embeddings> = {};
  for (const e of embeddings) {
    if (e.cluster_label != null) {
      (byCluster[e.cluster_label] ??= []).push(e);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-bold text-white">Cluster Explorer</h1>
      <p className="text-sm text-[#94a3b8]">
        Discover natural user archetypes from feature embeddings.
      </p>

      {runs.length > 0 && (
        <div className="flex items-center gap-3">
          <label className="text-sm text-[#94a3b8]">Clustering Run:</label>
          <select
            value={selectedRun}
            onChange={(e) => setSelectedRun(Number(e.target.value))}
            className="bg-[#1e293b] border border-[#334155] rounded px-2 py-1 text-white text-sm"
          >
            {runs.map((r, i) => (
              <option key={r.id} value={i}>
                {r.algorithm} ({r.n_clusters} clusters, sil={r.metric_value?.toFixed(3)})
              </option>
            ))}
          </select>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {clusters.map((c) => {
          const members = byCluster[c.label] ?? [];
          return (
            <div key={c.label} className="card flex flex-col gap-2">
              <div className="flex items-center justify-between">
                <h3 className="text-white font-semibold">{c.name}</h3>
                <span className="badge badge-blue">{c.n_users} users</span>
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs text-[#94a3b8]">
                <span>Avg Rating: <span className="text-white">{c.avg_rating.toFixed(0)}</span></span>
                <span>Max Rating: <span className="text-white">{c.avg_max_rating.toFixed(0)}</span></span>
                <span>Growth Vel: <span className="text-[#34d399]">{c.avg_growth_velocity > 0 ? "+" : ""}{c.avg_growth_velocity.toFixed(1)}</span></span>
                <span>Growth Accel: <span className={c.avg_growth_acceleration >= 0 ? "text-[#34d399]" : "text-[#fca5a5]"}>{c.avg_growth_acceleration.toFixed(1)}</span></span>
                <span>Contests: <span className="text-white">{c.avg_contests.toFixed(0)}</span></span>
                <span>Solved: <span className="text-white">{c.avg_solved.toFixed(0)}</span></span>
                <span>Tag Diversity: <span className="text-white">{c.avg_tag_diversity.toFixed(0)}</span></span>
                <span>Volatility: <span className="text-[#fbbf24]">{c.avg_volatility.toFixed(1)}</span></span>
                <span>Subs/Day: <span className="text-white">{c.avg_submissions_per_day.toFixed(2)}</span></span>
                <span>Inactivity: <span className="text-[#fca5a5]">{c.avg_inactivity_streak.toFixed(0)}d</span></span>
              </div>
              {Object.keys(c.dominant_tags).length > 0 && (
                <div>
                  <span className="text-xs text-[#64748b]">Top Tags: </span>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {Object.entries(c.dominant_tags).slice(0, 5).map(([tag, val]) => (
                      <span key={tag} className="badge badge-gray text-xs">
                        {tag.replace("tag_", "")} {val > 0 ? `${(val * 100).toFixed(0)}%` : ""}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {members.length > 0 && (
                <div>
                  <span className="text-xs text-[#64748b]">Top members: </span>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {members.slice(0, 10).map((m) => (
                      <span key={m.user_id} className="text-xs text-[#94a3b8]">
                        {m.handle} ({m.current_rating})
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {clusters.length === 0 && (
        <div className="card text-center py-8">
          <p className="text-[#64748b] text-sm">No clusters found. Run embeddings + clustering from the research loop.</p>
        </div>
      )}
    </div>
  );
}
