"use client";

import { usePathname } from "next/navigation";

export default function MainLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  const groups = [
    {
      label: "Learn",
      links: [
        { href: "/", label: "Dashboard", icon: "🏠" },
        { href: "/3d", label: "3D Explorer", icon: "🌐" },
        { href: "/expert-pathways", label: "The Path to 2400", icon: "🗺️" },
      ],
    },
    {
      label: "Patterns",
      links: [
        { href: "/breakthroughs", label: "Breakthroughs", icon: "🚀" },
        { href: "/plateaus", label: "Plateaus & Growth", icon: "📊" },
        { href: "/clusters", label: "Coder Archetypes", icon: "👥" },
      ],
    },
    {
      label: "Data",
      links: [
        { href: "/trajectories", label: "User Trajectories", icon: "📈" },
        { href: "/skill-graph", label: "Skill Graph", icon: "🔗" },
        { href: "/predictions", label: "Predictions", icon: "🎯" },
      ],
    },
    {
      label: "Research",
      links: [
        { href: "/activity", label: "Activity Log", icon: "⚡" },
        { href: "/hypotheses", label: "Hypotheses", icon: "❓" },
        { href: "/models", label: "Models", icon: "🧠" },
      ],
    },
  ];

  return (
    <>
      <aside className="w-56 min-h-screen bg-[#0f172a] border-r border-[#1e293b] p-4 flex flex-col gap-4 shrink-0">
        <div className="text-base font-bold text-white px-3 pt-2 leading-tight">
          Codeforces<br />Mastery Guide
        </div>
        {groups.map((g) => (
          <div key={g.label}>
            <div className="text-[10px] font-semibold text-[#475569] uppercase tracking-wider px-3 mb-1">
              {g.label}
            </div>
            {g.links.map((l) => (
              <a
                key={l.href}
                href={l.href}
                className={`flex items-center gap-2.5 px-3 py-1.5 rounded-lg text-sm transition-colors ${
                  pathname === l.href
                    ? "text-white bg-[#1e293b]"
                    : "text-[#94a3b8] hover:text-white hover:bg-[#1e293b]"
                }`}
              >
                <span className="text-xs">{l.icon}</span>
                {l.label}
              </a>
            ))}
          </div>
        ))}
      </aside>
      <main className="flex-1 p-6 overflow-auto min-h-screen">{children}</main>
    </>
  );
}
