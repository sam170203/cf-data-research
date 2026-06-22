"use client";

import { useEffect, useState } from "react";

const API = "/api";

interface TagFreq {
  [tag: string]: number;
}

interface BreakthroughDetail {
  key: string;
  description: string;
  total_events: number;
  avg_gain?: number;
  top_events?: Record<string, unknown>[];
  pre_breakthrough_pattern?: {
    avg_submissions?: number;
    avg_solved?: number;
    avg_solve_rate?: number;
    avg_difficulty?: number;
    dominant_tags?: string[];
    tag_frequency?: TagFreq;
  };
  strongest_predictors?: string[];
}

interface PlateauPattern {
  n_users: number;
  avg_change: number;
  avg_contests: number;
  avg_submissions: number;
  avg_solved: number;
  avg_solve_rate: number;
  avg_difficulty: number;
  dominant_tags: string[];
}

interface PlateauDetail {
  plateau_users: number;
  growing_users: number;
  plateau_pattern: PlateauPattern | Record<string, never>;
  growing_pattern: PlateauPattern | Record<string, never>;
  plateau_warning_signals: string[];
  growth_indicators: string[];
}

interface BreakthroughPlateauData {
  breakthrough_150_90d: BreakthroughDetail;
  breakthrough_300_180d: BreakthroughDetail;
  breakthrough_500_overall: BreakthroughDetail;
  plateau_20_180d: PlateauDetail;
}

export default function PlateausPage() {
  const [data, setData] = useState<BreakthroughPlateauData | null>(null);

  useEffect(() => {
    fetch(`${API}/research/breakthrough-plateau`).then((r) => r.json()).then(setData);
  }, []);

  if (!data) {
    return (
      <div className="flex flex-col gap-6">
        <h1 className="text-2xl font-bold text-white">Breakthrough & Plateau Analysis</h1>
        <p className="text-sm text-[#94a3b8]">Loading...</p>
      </div>
    );
  }

  const b150 = data.breakthrough_150_90d;
  const b300 = data.breakthrough_300_180d;
  const b500 = data.breakthrough_500_overall;
  const plat = data.plateau_20_180d;

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-bold text-white">Breakthrough & Plateau Analysis</h1>
      <p className="text-sm text-[#94a3b8]">
        Data-driven patterns from rating history and submission data across {325} users.
      </p>

      {/* Summary stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="card">
          <div className="stat-label">+150 in 90d</div>
          <div className="stat-value text-[#60a5fa]">{b150.total_events}</div>
        </div>
        <div className="card">
          <div className="stat-label">+300 in 180d</div>
          <div className="stat-value text-[#34d399]">{b300.total_events}</div>
        </div>
        <div className="card">
          <div className="stat-label">+500 Overall</div>
          <div className="stat-value text-[#fbbf24]">{b500.total_events}</div>
        </div>
        <div className="card">
          <div className="stat-label">Plateau Users</div>
          <div className="stat-value text-[#fca5a5]">{plat.plateau_users}</div>
        </div>
      </div>

      {/* Breakthrough patterns */}
      <div>
        <h2 className="text-lg font-semibold text-white mb-3">Breakthrough Patterns</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[b150, b300, b500].map((bt) => {
            const pattern = bt.pre_breakthrough_pattern;
            return (
              <div key={bt.key} className="card">
                <h3 className="text-sm font-semibold text-white mb-2">{bt.description}</h3>
                <p className="text-xs text-[#94a3b8] mb-3">{bt.total_events} events, avg gain +{bt.avg_gain}</p>
                {pattern && (
                  <div className="text-xs space-y-1">
                    <div className="flex justify-between">
                      <span className="text-[#64748b]">Avg difficulty</span>
                      <span className="text-white">{pattern.avg_difficulty}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-[#64748b]">Solve rate</span>
                      <span className="text-white">{pattern.avg_solve_rate}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-[#64748b]">Avg solved</span>
                      <span className="text-white">{pattern.avg_solved}</span>
                    </div>
                    <div className="mt-2">
                      <span className="text-[#64748b]">Top tags:</span>
                      <div className="flex flex-wrap gap-1 mt-1">
                        {(pattern.dominant_tags ?? []).slice(0, 6).map((tag) => (
                          <span key={tag} className="px-1.5 py-0.5 bg-[#1e293b] rounded text-[#60a5fa]">{tag}</span>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Plateau vs Growing comparison */}
      <div>
        <h2 className="text-lg font-semibold text-white mb-3">Plateau vs Growing (180-day windows)</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="card">
            <h3 className="text-sm font-semibold text-[#fca5a5] mb-2">Plateau Pattern ({plat.plateau_users} users)</h3>
            {plat.plateau_pattern && plat.plateau_pattern.n_users > 0 ? (
              <div className="text-xs space-y-1">
                <div className="flex justify-between">
                  <span className="text-[#64748b]">Avg change</span>
                  <span className="text-white">{plat.plateau_pattern.avg_change}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#64748b]">Avg contests</span>
                  <span className="text-white">{plat.plateau_pattern.avg_contests}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#64748b]">Avg difficulty</span>
                  <span className="text-white">{plat.plateau_pattern.avg_difficulty}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#64748b]">Avg solve rate</span>
                  <span className="text-white">{plat.plateau_pattern.avg_solve_rate}</span>
                </div>
                <div className="mt-2">
                  <span className="text-[#64748b]">Tags:</span>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {plat.plateau_pattern.dominant_tags?.slice(0, 6).map((tag) => (
                      <span key={tag} className="px-1.5 py-0.5 bg-[#1e293b] rounded text-[#94a3b8]">{tag}</span>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <p className="text-xs text-[#64748b]">No plateau users detected in current data</p>
            )}
          </div>
          <div className="card">
            <h3 className="text-sm font-semibold text-[#34d399] mb-2">Growing Pattern ({plat.growing_users} users)</h3>
            {plat.growing_pattern && plat.growing_pattern.n_users > 0 ? (
              <div className="text-xs space-y-1">
                <div className="flex justify-between">
                  <span className="text-[#64748b]">Avg change</span>
                  <span className="text-white">{plat.growing_pattern.avg_change}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#64748b]">Avg contests</span>
                  <span className="text-white">{plat.growing_pattern.avg_contests}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#64748b]">Avg difficulty</span>
                  <span className="text-white">{plat.growing_pattern.avg_difficulty}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#64748b]">Avg solve rate</span>
                  <span className="text-white">{plat.growing_pattern.avg_solve_rate}</span>
                </div>
                <div className="mt-2">
                  <span className="text-[#64748b]">Tags:</span>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {plat.growing_pattern.dominant_tags?.slice(0, 6).map((tag) => (
                      <span key={tag} className="px-1.5 py-0.5 bg-[#1e293b] rounded text-[#34d399]">{tag}</span>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <p className="text-xs text-[#64748b]">No growing users detected</p>
            )}
          </div>
        </div>
      </div>

      {/* Warning signals & Growth indicators */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="card">
          <h3 className="text-sm font-semibold text-[#fca5a5] mb-2">Plateau Warning Signals</h3>
          <ul className="text-xs text-[#94a3b8] space-y-1.5">
            {plat.plateau_warning_signals.map((s, i) => (
              <li key={i} className="flex items-start gap-2">
                <span className="text-[#fca5a5] mt-0.5">•</span>
                <span>{s}</span>
              </li>
            ))}
          </ul>
        </div>
        <div className="card">
          <h3 className="text-sm font-semibold text-[#34d399] mb-2">Growth Indicators</h3>
          <ul className="text-xs text-[#94a3b8] space-y-1.5">
            {plat.growth_indicators.map((s, i) => (
              <li key={i} className="flex items-start gap-2">
                <span className="text-[#34d399] mt-0.5">•</span>
                <span>{s}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Strongest predictors */}
      <div>
        <h2 className="text-lg font-semibold text-white mb-3">Strongest Breakthrough Predictors</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[b150, b300, b500].map((bt) => (
            <div key={bt.key} className="card">
              <h3 className="text-xs font-semibold text-[#94a3b8] mb-2">{bt.description}</h3>
              <div className="flex flex-wrap gap-1">
                {(bt.strongest_predictors ?? []).slice(0, 5).map((tag) => (
                  <span key={tag} className="px-1.5 py-0.5 bg-[#1e293b] rounded text-[#fbbf24] text-xs">{tag}</span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
