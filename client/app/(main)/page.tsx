"use client";

import { useEffect, useState } from "react";

const API = "/api";

/* ── Types ─────────────────────────────────────────────── */
interface Q1Data {
  future_experts: number;
  expert_below_1400: {
    tag_frequency: Record<string, number>;
    avg_difficulty: number;
    solve_rate: number;
    avg_submissions_per_user: number;
  };
  never_expert: {
    tag_frequency: Record<string, number>;
    avg_difficulty: number;
    solve_rate: number;
    avg_submissions_per_user: number;
  };
}
interface SubSummary {
  samples: number;
  avg_submissions_per_user: number;
  avg_difficulty: number;
  solve_rate: number;
  most_common_tags: string[];
}
interface Q2Data {
  breakthrough_events: number;
  before_breakthrough: SubSummary;
  typical_6mo: SubSummary;
}
interface Q3Data {
  before_gain_300: number;
  before_gain_500: number;
  gain_300_pattern: SubSummary;
  gain_500_pattern: SubSummary;
  no_gain_baseline: SubSummary;
}
interface Q4Data {
  plateau_events: number;
  growing_events: number;
  plateau_pattern: SubSummary;
  growing_pattern: SubSummary;
}
interface BPData {
  plateau_20_180d: {
    plateau_users: number;
    growing_users: number;
    plateau_warning_signals: string[];
    growth_indicators: string[];
  };
}
interface TrajQ {
  q1_future_experts: Q1Data;
  q2_before_breakthrough: Q2Data;
  q3_before_large_gain: Q3Data;
  q4_before_plateau: Q4Data;
}

interface Overview { users: number; submissions: number; }

/* ── Components ────────────────────────────────────────── */
function StatCard({ label, value, color, small }: { label: string; value: number | string; color?: string; small?: boolean }) {
  return (
    <div className={`card ${small ? "!p-3" : ""}`}>
      <div className="stat-label">{label}</div>
      <div className={`${small ? "text-xl" : "stat-value"}`} style={{ color: color ?? "#e2e8f0" }}>{value}</div>
    </div>
  );
}

function TagRow({ tags, color }: { tags: [string, number][]; color: string }) {
  return (
    <div className="flex flex-wrap gap-1 mt-2">
      {tags.map(([t]) => (
        <span key={t} className="px-2 py-0.5 bg-[#1e293b] rounded text-xs" style={{ color }}>{t}</span>
      ))}
    </div>
  );
}

function InsightCard({ title, body, color = "#60a5fa" }: { title: string; body: string; color?: string }) {
  return (
    <div className="card border-l-4" style={{ borderLeftColor: color }}>
      <div className="text-xs font-semibold mb-1" style={{ color }}>{title}</div>
      <div className="text-sm text-[#e2e8f0] leading-relaxed">{body}</div>
    </div>
  );
}

/* ── Main Dashboard ────────────────────────────────────── */
export default function Dashboard() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [q, setQ] = useState<TrajQ | null>(null);
  const [bp, setBp] = useState<BPData | null>(null);
  const [pathways, setPathways] = useState<any>(null);

  useEffect(() => {
    fetch(`${API}/metrics`).then(r => r.json()).then(d => setOverview({ users: d.users ?? 0, submissions: d.submissions ?? 0 }));
    fetch(`${API}/research/trajectories/questions`).then(r => r.json()).then(setQ);
    fetch(`${API}/research/breakthrough-plateau`).then(r => r.json()).then(setBp);
    fetch(`${API}/research/expert-pathways`).then(r => r.json()).then(setPathways);
  }, []);

  const q1 = q?.q1_future_experts;
  const q2 = q?.q2_before_breakthrough;
  const q3 = q?.q3_before_large_gain;
  const q4 = q?.q4_before_plateau;
  const plat = bp?.plateau_20_180d;

  return (
    <div className="flex flex-col gap-8 max-w-5xl">

      {/* ── HERO ─────────────────────────────────────── */}
      <div className="text-center py-6">
        <h1 className="text-3xl font-bold text-white mb-3">
          How to Master Competitive Programming
        </h1>
        <p className="text-sm text-[#94a3b8] max-w-2xl mx-auto leading-relaxed">
          We analyzed <strong className="text-white">{overview?.users ?? "…"}</strong> Codeforces users 
          and <strong className="text-white">{(overview?.submissions ?? 0).toLocaleString()}</strong> submissions 
          to find out what separates top coders from everyone else. Here is what we learned.
        </p>
      </div>

      {/* ── STEP 1: THE PATH ──────────────────────────── */}
      <section>
        <div className="flex items-center gap-3 mb-4">
          <span className="text-2xl">🗺️</span>
          <div>
            <h2 className="text-xl font-bold text-white">Step 1: What to Learn</h2>
            <p className="text-xs text-[#94a3b8]">The most common tag progression to each rating level</p>
          </div>
        </div>

        {pathways && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            {["specialist", "expert", "candidate_master", "master"].map((key) => {
              const m = pathways[key];
              if (!m) return null;
              const firstTags = (m.common_first_tags ?? []).slice(0, 6);
              const topTransition = (m.most_common_transitions ?? [])[0];
              return (
                <div key={key} className="card">
                  <div className="text-xs text-[#64748b] uppercase tracking-wider mb-1">→ {m.name}</div>
                  <div className="text-lg font-bold text-white mb-1">{m.total_users} users</div>
                  {firstTags.length > 0 && (
                    <>
                      <div className="text-xs text-[#94a3b8] mb-1">Most solved tags before this level:</div>
                      <div className="flex flex-wrap gap-1 mb-2">
                        {firstTags.map((t: any) => (
                          <span key={t.tag} className="px-2 py-0.5 bg-[#1e293b] rounded text-xs text-[#60a5fa]">{t.tag}</span>
                        ))}
                      </div>
                    </>
                  )}
                  {topTransition && (
                    <div className="text-xs text-[#64748b]">
                      Top transition: <span className="text-[#fbbf24]">{topTransition.path}</span>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        <InsightCard
          color="#a78bfa"
          title="Actionable Takeaway"
          body="Start with brute force, math, greedy, and implementation problems. As you improve, layer in DFS, graphs, DP, and data structures. Most top coders follow this exact progression — don't jump to advanced topics before mastering the basics."
        />
      </section>

      {/* ── STEP 2: BUILD HABITS ──────────────────────── */}
      <section>
        <div className="flex items-center gap-3 mb-4">
          <span className="text-2xl">📈</span>
          <div>
            <h2 className="text-xl font-bold text-white">Step 2: Build the Right Habits</h2>
            <p className="text-xs text-[#94a3b8]">How future experts practiced while still below 1400 rating</p>
          </div>
        </div>

        {q1 && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
            <StatCard label="Future Experts" value={q1.future_experts} color="#34d399" small />
            <StatCard label="Subs/User (experts)" value={q1.expert_below_1400.avg_submissions_per_user} color="#60a5fa" small />
            <StatCard label="Avg Difficulty" value={q1.expert_below_1400.avg_difficulty} color="#fbbf24" small />
            <StatCard label="Solve Rate" value={q1.expert_below_1400.solve_rate} color="#34d399" small />
          </div>
        )}

        {q1 && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div className="card">
              <div className="text-xs font-semibold text-[#34d399] mb-2">Future Experts (while below 1400)</div>
              <div className="text-xs space-y-1">
                <div className="flex justify-between"><span className="text-[#64748b]">Avg submissions/user</span><span className="text-white">{q1.expert_below_1400.avg_submissions_per_user}</span></div>
                <div className="flex justify-between"><span className="text-[#64748b]">Avg difficulty solved</span><span className="text-white">{q1.expert_below_1400.avg_difficulty}</span></div>
                <div className="flex justify-between"><span className="text-[#64748b]">Solve rate</span><span className="text-white">{q1.expert_below_1400.solve_rate}</span></div>
              </div>
              <TagRow tags={Object.entries(q1.expert_below_1400.tag_frequency).slice(0, 10)} color="#34d399" />
            </div>
            <div className="card">
              <div className="text-xs font-semibold text-[#fca5a5] mb-2">Never Reached Expert</div>
              <div className="text-xs space-y-1">
                <div className="flex justify-between"><span className="text-[#64748b]">Avg submissions/user</span><span className="text-white">{q1.never_expert.avg_submissions_per_user}</span></div>
                <div className="flex justify-between"><span className="text-[#64748b]">Avg difficulty solved</span><span className="text-white">{q1.never_expert.avg_difficulty}</span></div>
                <div className="flex justify-between"><span className="text-[#64748b]">Solve rate</span><span className="text-white">{q1.never_expert.solve_rate}</span></div>
              </div>
              <TagRow tags={Object.entries(q1.never_expert.tag_frequency).slice(0, 10)} color="#fca5a5" />
            </div>
          </div>
        )}

        <InsightCard
          color="#34d399"
          title="Actionable Takeaway"
          body="Future experts solved problems at ~1470 difficulty while still below 1400 rating — always reaching slightly above their level. They practiced broadly across implementation, math, greedy, DP, sortings, binary search, strings, and data structures. The users who never reached expert solved almost no problems below 1400. The message: solve lots of problems across many tags, always slightly above your comfort zone."
        />
      </section>

      {/* ── STEP 3: BREAKTHROUGHS ─────────────────────── */}
      <section>
        <div className="flex items-center gap-3 mb-4">
          <span className="text-2xl">🚀</span>
          <div>
            <h2 className="text-xl font-bold text-white">Step 3: What Happens Before a Breakthrough</h2>
            <p className="text-xs text-[#94a3b8]">Patterns in the 6 months before rapid rating gains</p>
          </div>
        </div>

        {q2 && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
            <StatCard label="Breakthroughs (+150/90d)" value={q2.breakthrough_events} color="#fbbf24" small />
            <StatCard label="6mo Subs Before BT" value={q2.before_breakthrough.avg_submissions_per_user} color="#60a5fa" small />
            <StatCard label="Avg Difficulty Before BT" value={q2.before_breakthrough.avg_difficulty} color="#a78bfa" small />
            <StatCard label="Typical 6mo Difficulty" value={q2.typical_6mo.avg_difficulty} color="#64748b" small />
          </div>
        )}

        {q3 && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
            <div className="card">
              <div className="text-xs font-semibold text-[#60a5fa] mb-2">Before +300 Gain</div>
              <div className="text-xs space-y-1">
                <div className="flex justify-between"><span className="text-[#64748b]">Subs/user</span><span className="text-white">{q3.gain_300_pattern.avg_submissions_per_user}</span></div>
                <div className="flex justify-between"><span className="text-[#64748b]">Avg difficulty</span><span className="text-white">{q3.gain_300_pattern.avg_difficulty}</span></div>
                <div className="flex justify-between"><span className="text-[#64748b]">Solve rate</span><span className="text-white">{q3.gain_300_pattern.solve_rate}</span></div>
              </div>
              <TagRow tags={q3.gain_300_pattern.most_common_tags.slice(0, 6).map((t: string) => [t, 0])} color="#60a5fa" />
            </div>
            <div className="card">
              <div className="text-xs font-semibold text-[#a78bfa] mb-2">Before +500 Gain</div>
              <div className="text-xs space-y-1">
                <div className="flex justify-between"><span className="text-[#64748b]">Subs/user</span><span className="text-white">{q3.gain_500_pattern.avg_submissions_per_user}</span></div>
                <div className="flex justify-between"><span className="text-[#64748b]">Avg difficulty</span><span className="text-white">{q3.gain_500_pattern.avg_difficulty}</span></div>
                <div className="flex justify-between"><span className="text-[#64748b]">Solve rate</span><span className="text-white">{q3.gain_500_pattern.solve_rate}</span></div>
              </div>
              <TagRow tags={q3.gain_500_pattern.most_common_tags.slice(0, 6).map((t: string) => [t, 0])} color="#a78bfa" />
            </div>
            <div className="card">
              <div className="text-xs font-semibold text-[#64748b] mb-2">No Gain (Baseline)</div>
              <div className="text-xs space-y-1">
                <div className="flex justify-between"><span className="text-[#64748b]">Subs/user</span><span className="text-white">{q3.no_gain_baseline.avg_submissions_per_user}</span></div>
                <div className="flex justify-between"><span className="text-[#64748b]">Avg difficulty</span><span className="text-white">{q3.no_gain_baseline.avg_difficulty}</span></div>
                <div className="flex justify-between"><span className="text-[#64748b]">Solve rate</span><span className="text-white">{q3.no_gain_baseline.solve_rate}</span></div>
              </div>
              <TagRow tags={q3.no_gain_baseline.most_common_tags.slice(0, 6).map((t: string) => [t, 0])} color="#64748b" />
            </div>
          </div>
        )}

        <InsightCard
          color="#fbbf24"
          title="Actionable Takeaway"
          body="Before a breakthrough (+150 rating in 90 days), users submitted ~308 problems (avg difficulty ~1600). Before a +500 single-contest gain, they submitted ~107 problems at ~1700 avg difficulty. The pattern: sustained practice at a difficulty slightly above your current rating is the best predictor of a breakthrough. Users who barely practice see no gains."
        />
      </section>

      {/* ── STEP 4: AVOID PLATEAUS ────────────────────── */}
      <section>
        <div className="flex items-center gap-3 mb-4">
          <span className="text-2xl">⚠️</span>
          <div>
            <h2 className="text-xl font-bold text-white">Step 4: Avoid These Traps</h2>
            <p className="text-xs text-[#94a3b8]">What plateauing users do differently</p>
          </div>
        </div>

        {q4 && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
            <StatCard label="Plateau Detected" value={q4.plateau_events} color="#fca5a5" small />
            <StatCard label="Still Growing" value={q4.growing_events} color="#34d399" small />
            <StatCard label="Plat avg subs/6mo" value={q4.plateau_pattern.avg_submissions_per_user} color="#fca5a5" small />
            <StatCard label="Grow avg subs/6mo" value={q4.growing_pattern.avg_submissions_per_user} color="#34d399" small />
          </div>
        )}

        {plat && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div className="card">
              <div className="text-xs font-semibold text-[#fca5a5] mb-2">Warning Signals</div>
              <ul className="text-xs text-[#94a3b8] space-y-1.5">
                {plat.plateau_warning_signals.map((s: string, i: number) => (
                  <li key={i} className="flex items-start gap-2"><span className="text-[#fca5a5] mt-0.5">•</span><span>{s}</span></li>
                ))}
              </ul>
            </div>
            <div className="card">
              <div className="text-xs font-semibold text-[#34d399] mb-2">Growth Indicators</div>
              <ul className="text-xs text-[#94a3b8] space-y-1.5">
                {plat.growth_indicators.map((s: string, i: number) => (
                  <li key={i} className="flex items-start gap-2"><span className="text-[#34d399] mt-0.5">•</span><span>{s}</span></li>
                ))}
              </ul>
            </div>
          </div>
        )}

        <InsightCard
          color="#fca5a5"
          title="Actionable Takeaway"
          body="Plateauing users practice less, solve fewer unique tags, and attempt lower-difficulty problems than growing users. To avoid stagnation: increase problem difficulty over time, practice diverse tags, participate in contests consistently, and minimize gaps between practice sessions. The data proves that growth comes from consistent, varied, above-level practice."
        />
      </section>

      {/* ── FINAL SUMMARY ─────────────────────────────── */}
      <section>
        <div className="flex items-center gap-3 mb-4">
          <span className="text-2xl">🎯</span>
          <div>
            <h2 className="text-xl font-bold text-white">The 4-Step Formula (Backed by Data)</h2>
            <p className="text-xs text-[#94a3b8]">What 325 top Codeforces users teach us</p>
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="card border-l-4" style={{ borderLeftColor: "#a78bfa" }}>
            <div className="text-xs font-semibold text-[#a78bfa] mb-1">1. Learn in Order</div>
            <div className="text-sm text-[#e2e8f0]">Start with brute force, math, greedy, implementation → add DFS, graphs, DP → advanced topics like flows, FFT, string structures only at higher ratings.</div>
          </div>
          <div className="card border-l-4" style={{ borderLeftColor: "#34d399" }}>
            <div className="text-xs font-semibold text-[#34d399] mb-1">2. Practice Above Your Level</div>
            <div className="text-sm text-[#e2e8f0]">Future experts solved ~1470-difficulty problems while rated below 1400. Always reach slightly above your current rating.</div>
          </div>
          <div className="card border-l-4" style={{ borderLeftColor: "#fbbf24" }}>
            <div className="text-xs font-semibold text-[#fbbf24] mb-1">3. Be Consistent</div>
            <div className="text-sm text-[#e2e8f0]">Before breakthroughs, users submitted ~300 problems in 6 months across many tags. Breakthroughs come from sustained effort, not bursts.</div>
          </div>
          <div className="card border-l-4" style={{ borderLeftColor: "#fca5a5" }}>
            <div className="text-xs font-semibold text-[#fca5a5] mb-1">4. Keep Challenging Yourself</div>
            <div className="text-sm text-[#e2e8f0]">Plateaus happen when you stop increasing difficulty and narrowing your tag range. Always push to harder problems and new topics.</div>
          </div>
        </div>
      </section>

      {/* ── EXPLORE MORE ──────────────────────────────── */}
      <section className="border-t border-[#1e293b] pt-6 mt-4">
        <h2 className="text-lg font-bold text-white mb-3">Dive Deeper</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <a href="/expert-pathways" className="card block hover:bg-[#1e293b] transition-colors">
            <div className="text-sm font-semibold text-white mb-1">🗺️ The Path to 2400</div>
            <div className="text-xs text-[#a78bfa]">Full tag progression for each milestone</div>
          </a>
          <a href="/breakthroughs" className="card block hover:bg-[#1e293b] transition-colors">
            <div className="text-sm font-semibold text-white mb-1">🚀 Breakthroughs</div>
            <div className="text-xs text-[#60a5fa]">Top events and patterns</div>
          </a>
          <a href="/plateaus" className="card block hover:bg-[#1e293b] transition-colors">
            <div className="text-sm font-semibold text-white mb-1">📊 Plateaus & Growth</div>
            <div className="text-xs text-[#fca5a5]">Detailed analysis</div>
          </a>
          <a href="/clusters" className="card block hover:bg-[#1e293b] transition-colors">
            <div className="text-sm font-semibold text-white mb-1">👥 Coder Archetypes</div>
            <div className="text-xs text-[#fbbf24]">Which type are you?</div>
          </a>
        </div>
      </section>
    </div>
  );
}
