"use client";

import { useEffect, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

const API = "/api";

interface Prediction {
  id: number;
  model_type: string;
  task_type: string;
  accuracy: number | null;
  f1_score: number | null;
  roc_auc: number | null;
  mae: number | null;
  rmse: number | null;
  r2: number | null;
  sample_size: number;
  feature_importance: Record<string, unknown> | null;
  created_at: string | null;
  run_count?: number;
  shap_values?: Record<string, unknown> | null;
}

const TASK_DISPLAY: Record<string, string> = {
  expert_6mo: "Expert in 6mo",
  cm_12mo: "Candidate Master in 12mo",
  master_12mo: "Master in 12mo",
  gain_100_90d: "+100 Rating in 90d",
  expert_12mo: "Expert in 12mo",
  plateau_risk: "Plateau Risk",
  rating_3mo: "Rating in 3mo",
  rating_6mo: "Rating in 6mo",
  rating_12mo: "Rating in 12mo",
  rating_90d: "Rating in 90d",
  rating_180d: "Rating in 180d",
};

export default function PredictionsPage() {
  const [latest, setLatest] = useState<Record<string, Prediction>>({});
  const [selected, setSelected] = useState<string>("");

  useEffect(() => {
    fetch(`${API}/research/predictions?limit=200`).then((r) => r.json()).then((d) => {
      setLatest(d.latest ?? {});
    });
  }, []);

  const tasks = Object.keys(latest);
  const current = selected || tasks[0] || "";
  const pred = latest[current];
  const fi = pred?.feature_importance as Record<string, unknown> | null;
  const features: { feature: string; importance: number }[] = [];
  if (fi?.features && Array.isArray(fi.features)) {
    features.push(...(fi.features as { feature: string; importance: number }[]));
  }

  const whyExplanation = features.slice(0, 6);

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-bold text-white">Prediction Center</h1>
      <p className="text-sm text-[#94a3b8]">
        Forecast user growth with explainable AI. Every prediction answers WHY.
      </p>

      <div className="flex items-center gap-3">
        <label className="text-sm text-[#94a3b8]">Task:</label>
        <select
          value={current}
          onChange={(e) => setSelected(e.target.value)}
          className="bg-[#1e293b] border border-[#334155] rounded px-2 py-1 text-white text-sm"
        >
          {tasks.map((t) => (
            <option key={t} value={t}>{TASK_DISPLAY[t] ?? t}</option>
          ))}
        </select>
      </div>

      {pred && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {pred.f1_score != null && (
              <div className="card">
                <div className="stat-label">F1 Score</div>
                <div className="stat-value text-[#60a5fa]">{pred.f1_score.toFixed(3)}</div>
              </div>
            )}
            {pred.accuracy != null && (
              <div className="card">
                <div className="stat-label">Accuracy</div>
                <div className="stat-value text-[#34d399]">{pred.accuracy.toFixed(3)}</div>
              </div>
            )}
            {pred.roc_auc != null && (
              <div className="card">
                <div className="stat-label">ROC AUC</div>
                <div className="stat-value text-[#a78bfa]">{pred.roc_auc.toFixed(3)}</div>
              </div>
            )}
            {pred.r2 != null && (
              <div className="card">
                <div className="stat-label">R²</div>
                <div className="stat-value text-[#fbbf24]">{pred.r2.toFixed(3)}</div>
              </div>
            )}
            {pred.mae != null && (
              <div className="card">
                <div className="stat-label">MAE</div>
                <div className="stat-value text-[#f472b6]">{pred.mae.toFixed(1)}</div>
              </div>
            )}
            <div className="card">
              <div className="stat-label">Sample Size</div>
              <div className="stat-value text-[#94a3b8]">{pred.sample_size}</div>
            </div>
            <div className="card">
              <div className="stat-label">Best Model</div>
              <div className="stat-value text-[#22d3ee]" style={{ fontSize: "1rem" }}>{pred.model_type}</div>
            </div>
          </div>

          {whyExplanation.length > 0 && (
            <div className="card">
              <h2 className="text-lg font-semibold text-white mb-3">
                Why does this model make its predictions?
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                {whyExplanation.map((f, i) => (
                  <div key={i} className="flex items-center gap-3 p-2 rounded-lg bg-[#1e293b]">
                    <div
                      className="w-1 h-8 rounded-full"
                      style={{ background: f.importance > 0 ? "#34d399" : "#fca5a5" }}
                    />
                    <div className="flex-1 min-w-0">
                      <div className="text-sm text-white truncate">{f.feature}</div>
                      <div className="text-xs text-[#64748b]">
                        {f.importance > 0
                          ? `Positive contributor (${f.importance.toFixed(3)})`
                          : `Negative factor (${f.importance.toFixed(3)})`}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {features.length > 0 && (
            <div className="card">
              <h2 className="text-lg font-semibold text-white mb-3">Feature Importance</h2>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart
                  data={features.slice(0, 15)}
                  layout="vertical"
                  margin={{ top: 5, right: 30, left: 120, bottom: 5 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                  <XAxis type="number" tick={{ fill: "#94a3b8", fontSize: 11 }} />
                  <YAxis dataKey="feature" type="category" tick={{ fill: "#94a3b8", fontSize: 10 }} width={120} />
                  <Tooltip
                    contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: "8px", color: "#e2e8f0" }}
                  />
                  <Bar dataKey="importance" fill="#60a5fa" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </>
      )}

      {!pred && (
        <div className="card text-center py-8">
          <p className="text-[#64748b] text-sm">No prediction data yet. Run the research loop to train models.</p>
        </div>
      )}
    </div>
  );
}
