"use client";

import { useEffect, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from "recharts";

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
}

const TASK_DISPLAY: Record<string, string> = {
  expert_6mo: "Expert (6mo)",
  cm_12mo: "Candidate Master (12mo)",
  master_12mo: "Master (12mo)",
  gain_100_90d: "+100 Rating (90d)",
  expert_12mo: "Expert (12mo)",
  plateau_risk: "Plateau Risk",
  rating_3mo: "Rating (3mo)",
  rating_6mo: "Rating (6mo)",
  rating_12mo: "Rating (12mo)",
  rating_90d: "Rating (90d)",
  rating_180d: "Rating (180d)",
};

function MetricChart({ data, metric, label, color }: {
  data: { task: string; value: number }[];
  metric: string;
  label: string;
  color: string;
}) {
  if (data.length === 0) return null;
  return (
    <div className="card">
      <h3 className="text-sm font-semibold text-white mb-3">{label}</h3>
      <ResponsiveContainer width="100%" height={250}>
        <BarChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
          <XAxis dataKey="task" tick={{ fill: "#94a3b8", fontSize: 10 }} angle={-20} textAnchor="end" height={60} />
          <YAxis tick={{ fill: "#94a3b8", fontSize: 11 }} />
          <Tooltip
            contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: "8px", color: "#e2e8f0" }}
          />
          <Bar dataKey="value" fill={color} radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export default function ModelsPage() {
  const [latest, setLatest] = useState<Record<string, Prediction>>({});
  const [byTask, setByTask] = useState<Record<string, Prediction[]>>({});
  const [selectedTask, setSelectedTask] = useState<string>("");

  useEffect(() => {
    fetch(`${API}/research/predictions?limit=200`).then((r) => r.json()).then((d) => {
      setLatest(d.latest ?? {});
      setByTask(d.by_task ?? {});
    });
  }, []);

  const tasks = Object.keys(latest);
  const selected = selectedTask || tasks[0] || "";

  const classificationData = tasks
    .filter((t) => latest[t]?.f1_score != null)
    .map((t) => ({ task: TASK_DISPLAY[t] ?? t, value: latest[t].f1_score as number }));
  const regressionData = tasks
    .filter((t) => latest[t]?.r2 != null)
    .map((t) => ({ task: TASK_DISPLAY[t] ?? t, value: latest[t].r2 as number }));
  const accuracyData = tasks
    .filter((t) => latest[t]?.accuracy != null)
    .map((t) => ({ task: TASK_DISPLAY[t] ?? t, value: latest[t].accuracy as number }));

  const taskRuns = byTask[selected] ?? [];

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-bold text-white">Model Comparison</h1>

      {/* Summary Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="card">
          <div className="stat-label">Classification Tasks</div>
          <div className="stat-value text-[#60a5fa]">
            {Object.keys(byTask).filter((t) => latest[t]?.task_type === "classification").length}
          </div>
        </div>
        <div className="card">
          <div className="stat-label">Regression Tasks</div>
          <div className="stat-value text-[#a78bfa]">
            {Object.keys(byTask).filter((t) => latest[t]?.task_type === "regression").length}
          </div>
        </div>
        <div className="card">
          <div className="stat-label">Total Runs</div>
          <div className="stat-value text-[#34d399]">
            {Object.values(byTask).reduce((s, r) => s + r.length, 0)}
          </div>
        </div>
      </div>

      {/* Chart Row */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <MetricChart data={classificationData} metric="f1" label="F1 Score (Classification)" color="#60a5fa" />
        <MetricChart data={regressionData} metric="r2" label="R² Score (Regression)" color="#34d399" />
      </div>
      {accuracyData.length > 0 && (
        <MetricChart data={accuracyData} metric="acc" label="Accuracy (Classification)" color="#a78bfa" />
      )}

      {/* Task Detail */}
      <div>
        <div className="flex items-center gap-3 mb-3">
          <h2 className="text-lg font-semibold text-white">Task Details</h2>
          <select
            value={selected}
            onChange={(e) => setSelectedTask(e.target.value)}
            className="bg-[#1e293b] border border-[#334155] rounded px-2 py-1 text-white text-sm"
          >
            {tasks.map((t) => (
              <option key={t} value={t}>{TASK_DISPLAY[t] ?? t} ({byTask[t]?.length ?? 0} runs)</option>
            ))}
          </select>
        </div>

        {taskRuns.length > 0 && (
          <div className="card overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[#94a3b8] border-b border-[#334155]">
                  <th className="text-left py-2 pr-4">Model</th>
                  <th className="text-right py-2 pr-4">Accuracy</th>
                  <th className="text-right py-2 pr-4">F1</th>
                  <th className="text-right py-2 pr-4">ROC AUC</th>
                  <th className="text-right py-2 pr-4">MAE</th>
                  <th className="text-right py-2 pr-4">R²</th>
                  <th className="text-right py-2">Samples</th>
                </tr>
              </thead>
              <tbody>
                {taskRuns.map((r, i) => (
                  <tr key={r.id ?? i} className="border-b border-[#1e293b] last:border-0">
                    <td className="py-2 pr-4 text-white">{r.model_type}</td>
                    <td className="py-2 pr-4 text-right">{r.accuracy?.toFixed(3) ?? "—"}</td>
                    <td className="py-2 pr-4 text-right">{r.f1_score?.toFixed(3) ?? "—"}</td>
                    <td className="py-2 pr-4 text-right">{r.roc_auc?.toFixed(3) ?? "—"}</td>
                    <td className="py-2 pr-4 text-right">{r.mae?.toFixed(1) ?? "—"}</td>
                    <td className="py-2 pr-4 text-right">{r.r2?.toFixed(3) ?? "—"}</td>
                    <td className="py-2 text-right text-[#94a3b8]">{r.sample_size}</td>
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
