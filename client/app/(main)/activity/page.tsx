"use client";

import { useEffect, useState } from "react";

const API = "/api";

interface ActivityEvent {
  type: string;
  description: string;
  detail: string;
  timestamp: string;
}

const typeColors: Record<string, string> = {
  hypothesis_generated: "badge-blue",
  hypothesis_tested: "badge-yellow",
  hypothesis_validated: "badge-green",
  pattern_discovered: "badge-purple",
  model_retrained: "badge-gray",
  report_generated: "badge-gray",
};

const typeLabels: Record<string, string> = {
  hypothesis_generated: "Generated",
  hypothesis_tested: "Tested",
  hypothesis_validated: "Validated",
  pattern_discovered: "Pattern",
  model_retrained: "Retrain",
  report_generated: "Report",
};

export default function ActivityPage() {
  const [events, setEvents] = useState<ActivityEvent[]>([]);
  const [filter, setFilter] = useState<string>("all");

  useEffect(() => {
    fetch(`${API}/research/activity-feed?limit=200`).then((r) => r.json()).then((d) => {
      setEvents(d.events ?? []);
    });
  }, []);

  const filtered = filter === "all" ? events : events.filter((e) => e.type === filter);
  const types = [...new Set(events.map((e) => e.type))];

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-bold text-white">Activity Feed</h1>

      <div className="flex gap-2 flex-wrap">
        <button onClick={() => setFilter("all")} className={`badge ${filter === "all" ? "badge-blue" : "badge-gray"} cursor-pointer`}>
          All ({events.length})
        </button>
        {types.map((t) => (
          <button key={t} onClick={() => setFilter(t)} className={`badge ${filter === t ? "badge-blue" : "badge-gray"} cursor-pointer`}>
            {typeLabels[t] ?? t} ({events.filter((e) => e.type === t).length})
          </button>
        ))}
      </div>

      <div className="card flex flex-col gap-2">
        {filtered.length === 0 && <p className="text-sm text-[#64748b]">No events</p>}
        {filtered.map((e, i) => (
          <div key={i} className="flex items-start gap-3 text-sm py-2 border-b border-[#1e293b] last:border-0">
            <span className={`badge ${typeColors[e.type] ?? "badge-gray"} shrink-0`}>
              {typeLabels[e.type] ?? e.type}
            </span>
            <div className="min-w-0 flex-1">
              <div className="text-white truncate">{e.description}</div>
              <div className="text-[#64748b] text-xs">{e.detail}</div>
            </div>
            {e.timestamp && (
              <div className="text-[#475569] text-xs shrink-0 w-32 text-right">
                {new Date(e.timestamp).toLocaleString()}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
