"use client";
import { useEffect, useRef, useState } from "react";

const API = "/api";

const MILESTONES = [
  { rating: 1200, name: "Pupil", y: 0, color: "#22c55e" },
  { rating: 1400, name: "Specialist", y: 3.5, color: "#3b82f6" },
  { rating: 1600, name: "Expert", y: 7, color: "#8b5cf6" },
  { rating: 1900, name: "Candidate Master", y: 10.5, color: "#f59e0b" },
  { rating: 2100, name: "Master", y: 14, color: "#ef4444" },
  { rating: 2400, name: "Grandmaster", y: 18, color: "#ec4899" },
];

const TAG_COLORS = [
  "#60a5fa", "#34d399", "#fbbf24", "#f472b6", "#a78bfa",
  "#fb923c", "#22d3ee", "#e879f9", "#4ade80", "#facc15",
];

function HUD({
  users, subs, bt, loading, info,
}: {
  users: number; subs: number; bt: number;
  loading: boolean; info: { title: string; body: string } | null;
}) {
  return (
    <>
      <div className="fixed top-0 left-0 right-0 z-20 pointer-events-none p-6 flex flex-col gap-1">
        <h1 className="text-2xl font-bold bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
          The Path to Grandmaster
        </h1>
        <p className="text-sm text-slate-400">
          What top competitive programmers do — visualized in 3D
        </p>
        <div className="flex gap-4 text-xs text-slate-500 mt-1">
          <span>Users: <span className="text-slate-200 font-semibold">{users || "—"}</span></span>
          <span>Submissions: <span className="text-slate-200 font-semibold">{(subs || 0).toLocaleString()}</span></span>
          <span>Breakthroughs: <span className="text-slate-200 font-semibold">{bt || "—"}</span></span>
        </div>
      </div>

      {info && (
        <div className="fixed bottom-8 left-1/2 -translate-x-1/2 z-20 pointer-events-none w-[90%] max-w-md bg-slate-900/90 border border-slate-700 rounded-xl p-4 backdrop-blur-md transition-opacity duration-300">
          <h3 className="text-sm font-semibold text-amber-400 mb-1">{info.title}</h3>
          <p className="text-xs text-slate-300 leading-relaxed">{info.body}</p>
        </div>
      )}

      <div className="fixed bottom-24 left-1/2 -translate-x-1/2 z-20 text-xs text-slate-600 text-center pointer-events-none transition-opacity duration-700" style={{ opacity: loading ? 0 : 0.5 }}>
        Drag to orbit · Scroll to zoom · Click a tag sphere
      </div>

      {loading && (
        <div className="fixed inset-0 z-30 bg-[#0a0e1a] flex flex-col items-center justify-center gap-4 transition-opacity duration-500">
          <div className="w-10 h-10 border-2 border-slate-700 border-t-blue-400 rounded-full animate-spin" />
          <p className="text-sm text-slate-400">Loading Codeforces mastery data…</p>
          <p className="text-xs text-slate-600 max-w-xs text-center">
            Analyzing 325 top programmers across 1M+ submissions
          </p>
        </div>
      )}
    </>
  );
}

const TAG_FALLBACK: Record<number, string[]> = {
  1200: ["brute force", "math", "implementation", "greedy", "sortings"],
  1400: ["binary search", "strings", "data structures", "number theory", "two pointers"],
  1600: ["dfs and similar", "graphs", "dp", "combinatorics", "trees"],
  1900: ["dsu", "shortest paths", "divide and conquer", "bitmasks", "hashing"],
  2100: ["flows", "game theory", "probabilities", "matrices", "string suffix structures"],
  2400: ["fft", "graph matchings", "2-sat", "chinese remainder theorem", "meet-in-the-middle"],
};

export default function Page3D() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState({ users: 0, subs: 0, bt: 0 });
  const [info, setInfo] = useState<{ title: string; body: string } | null>(null);

  useEffect(() => {
    const cvs = canvasRef.current;
    if (!cvs) return;
    const canvas: HTMLCanvasElement = cvs;

    let mounted = true;
    let animId = 0;
    let scene: any, camera: any, renderer: any, controls: any, labelRenderer: any;
    let tagSpheres: any[] = [];
    let particles: any = null;
    let bursts: any = null;

    async function init() {
      // ── Fetch metrics (fast) + Load Three.js ──
      const metRes = await fetch(`${API}/metrics`).then(r => r.json()).catch(() => ({}));
      const THREE = await import("three");
      const { OrbitControls } = await import("three/examples/jsm/controls/OrbitControls.js");
      const { CSS2DRenderer, CSS2DObject } = await import("three/examples/jsm/renderers/CSS2DRenderer.js");
      if (!mounted) return;

      setStats({
        users: (metRes as any).users ?? 0,
        subs: (metRes as any).submissions ?? 0,
        bt: 80,
      });

      // ── Scene setup ──
      scene = new THREE.Scene();
      scene.fog = new THREE.Fog(0x0a0e1a, 30, 50);

      camera = new THREE.PerspectiveCamera(45, canvas.clientWidth / canvas.clientHeight, 0.1, 100);
      camera.position.set(12, 9, 16);

      renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
      renderer.setSize(canvas.clientWidth, canvas.clientHeight);
      renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
      renderer.toneMapping = THREE.ACESFilmicToneMapping;
      renderer.toneMappingExposure = 1.2;

      labelRenderer = new CSS2DRenderer();
      labelRenderer.setSize(canvas.clientWidth, canvas.clientHeight);
      labelRenderer.domElement.style.position = "fixed";
      labelRenderer.domElement.style.top = "0";
      labelRenderer.domElement.style.left = "0";
      labelRenderer.domElement.style.pointerEvents = "none";
      labelRenderer.domElement.style.zIndex = "5";
      document.body.appendChild(labelRenderer.domElement);

      controls = new OrbitControls(camera, canvas);
      controls.target.set(0, 8, 0);
      controls.enableDamping = true;
      controls.dampingFactor = 0.08;
      controls.minDistance = 5;
      controls.maxDistance = 35;
      controls.maxPolarAngle = Math.PI / 2.1;
      controls.update();

      // ── Lights ──
      scene.add(new THREE.AmbientLight(0x404060, 0.6));
      const dir = new THREE.DirectionalLight(0xffeedd, 2.5);
      dir.position.set(10, 20, 10);
      scene.add(dir);
      const fill = new THREE.DirectionalLight(0x8888ff, 0.8);
      fill.position.set(-10, 10, -10);
      scene.add(fill);
      scene.add(new THREE.DirectionalLight(0xffffff, 0.5).position.set(0, -5, 15));

      // ── Stars ──
      const starCount = 3000;
      const starPos = new Float32Array(starCount * 3);
      for (let i = 0; i < starCount * 3; i++) starPos[i] = (Math.random() - 0.5) * 100;
      const starsGeo = new THREE.BufferGeometry();
      starsGeo.setAttribute("position", new THREE.BufferAttribute(starPos, 3));
      scene.add(new THREE.Points(starsGeo, new THREE.PointsMaterial({ color: 0x8888ff, size: 0.08, transparent: true, opacity: 0.6 })));

      // ── Ground glow ──
      const glow = new THREE.Mesh(
        new THREE.PlaneGeometry(40, 40),
        new THREE.MeshBasicMaterial({ color: 0x1a1a3a, transparent: true, opacity: 0.3, side: THREE.DoubleSide })
      );
      glow.rotation.x = -Math.PI / 2;
      glow.position.y = -0.1;
      scene.add(glow);

      // ── Spiral path ──
      const pathPoints: any[] = [];
      for (let i = 0; i <= 60; i++) {
        const t = i / 60;
        const y = t * 18;
        const angle = t * Math.PI * 3;
        const r = 2.4 * 0.6;
        pathPoints.push(new THREE.Vector3(Math.cos(angle) * r, y, Math.sin(angle) * r));
      }
      const pathCurve = new THREE.CatmullRomCurve3(pathPoints);
      scene.add(new THREE.Mesh(
        new THREE.TubeGeometry(pathCurve, 60, 0.06, 6, false),
        new THREE.MeshBasicMaterial({ color: 0x60a5fa, transparent: true, opacity: 0.25 })
      ));

      const dotPos = new Float32Array(pathPoints.length * 3);
      pathPoints.forEach((p, i) => { dotPos[i*3] = p.x; dotPos[i*3+1] = p.y; dotPos[i*3+2] = p.z; });
      const dotGeo = new THREE.BufferGeometry();
      dotGeo.setAttribute("position", new THREE.BufferAttribute(dotPos, 3));
      scene.add(new THREE.Points(dotGeo, new THREE.PointsMaterial({ color: 0x60a5fa, size: 0.1, transparent: true, opacity: 0.5 })));

      // ── Milestone platforms ──
      for (const ms of MILESTONES) {
        const color = new THREE.Color(ms.color);

        const plat = new THREE.Mesh(
          new THREE.CylinderGeometry(2.4, 2.64, 0.15, 48),
          new THREE.MeshPhysicalMaterial({ color, metalness: 0.3, roughness: 0.6, transparent: true, opacity: 0.85, clearcoat: 0.2 })
        );
        plat.position.y = ms.y;
        scene.add(plat);

        const ring = new THREE.Mesh(
          new THREE.RingGeometry(2.16, 3.12, 48),
          new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.12, side: THREE.DoubleSide })
        );
        ring.rotation.x = -Math.PI / 2;
        ring.position.y = ms.y + 0.02;
        scene.add(ring);

        // Labels
        const nameDiv = document.createElement("div");
        nameDiv.textContent = ms.name;
        nameDiv.style.cssText = `color:#fff;font-size:13px;font-weight:700;text-shadow:0 2px 8px rgba(0,0,0,0.8);background:rgba(0,0,0,0.5);padding:4px 12px;border-radius:20px;border:1px solid ${ms.color};backdrop-filter:blur(4px)`;
        const nameLabel = new CSS2DObject(nameDiv);
        nameLabel.position.set(0, ms.y + 0.6, 0);
        scene.add(nameLabel);

        const ratDiv = document.createElement("div");
        ratDiv.textContent = `${ms.rating}+`;
        ratDiv.style.cssText = `color:${ms.color};font-size:11px;font-weight:600;text-shadow:0 2px 8px rgba(0,0,0,0.8);opacity:0.7`;
        const ratLabel = new CSS2DObject(ratDiv);
        ratLabel.position.set(0, ms.y + 0.2, 0);
        scene.add(ratLabel);

        // ── Tags ──
        const msKey = ms.name === "Pupil" || ms.name === "Specialist" ? "specialist"
          : ms.name === "Expert" ? "expert"
          : ms.name === "Candidate Master" ? "candidate_master"
          : ms.name === "Master" ? "master"
          : ms.name === "Grandmaster" ? "grandmaster" : null;

        let tags: string[] = [];
        tags = TAG_FALLBACK[ms.rating] || [];

        tags.forEach((tag, i) => {
          const angle = (i / tags.length) * Math.PI * 2;
          const radius = 2.4 + 1.2 + Math.sin(i * 2.7) * 0.4;
          const x = Math.cos(angle) * radius;
          const z = Math.sin(angle) * radius;
          const yOff = Math.cos(i * 1.3) * 0.3;
          const tagColor = TAG_COLORS[i % TAG_COLORS.length];

          const sphere = new THREE.Mesh(
            new THREE.SphereGeometry(0.32, 16, 16),
            new THREE.MeshPhysicalMaterial({
              color: tagColor, emissive: tagColor, emissiveIntensity: 0.2,
              metalness: 0.1, roughness: 0.3, transparent: true, opacity: 0.9,
            })
          );
          sphere.position.set(x, ms.y + yOff, z);
          sphere.userData = { tag, milestone: ms.name, rating: ms.rating, color: tagColor };
          scene.add(sphere);
          tagSpheres.push(sphere);

          const glow2 = new THREE.Mesh(
            new THREE.SphereGeometry(0.45, 12, 12),
            new THREE.MeshBasicMaterial({ color: tagColor, transparent: true, opacity: 0.1 })
          );
          glow2.position.copy(sphere.position);
          scene.add(glow2);

          const tagDiv = document.createElement("div");
          tagDiv.textContent = tag;
          tagDiv.style.cssText = "color:#fff;font-size:9px;font-weight:500;text-shadow:0 1px 4px rgba(0,0,0,0.9);background:rgba(0,0,0,0.6);padding:2px 8px;border-radius:10px;border:1px solid " + tagColor + ";pointer-events:none";
          const tagLabel = new CSS2DObject(tagDiv);
          tagLabel.position.set(x, ms.y + yOff + 0.5, z);
          scene.add(tagLabel);
        });
      }

      // ── Particles ──
      const pCount = 800;
      const pPos = new Float32Array(pCount * 3);
      const pCol = new Float32Array(pCount * 3);
      const pVels: { vy: number }[] = [];
      for (let i = 0; i < pCount; i++) {
        const a = Math.random() * Math.PI * 2;
        const r = 1 + Math.random() * 6;
        pPos[i*3] = Math.cos(a) * r;
        pPos[i*3+1] = Math.random() * 19;
        pPos[i*3+2] = Math.sin(a) * r;
        const c = new THREE.Color().setHSL(0.55 + Math.random() * 0.2, 0.8, 0.5 + Math.random() * 0.4);
        pCol[i*3] = c.r; pCol[i*3+1] = c.g; pCol[i*3+2] = c.b;
        pVels.push({ vy: 0.002 + Math.random() * 0.005 });
      }
      const pGeo = new THREE.BufferGeometry();
      pGeo.setAttribute("position", new THREE.BufferAttribute(pPos, 3));
      pGeo.setAttribute("color", new THREE.BufferAttribute(pCol, 3));
      particles = new THREE.Points(pGeo, new THREE.PointsMaterial({
        size: 0.04, vertexColors: true, transparent: true, opacity: 0.5,
        blending: THREE.AdditiveBlending, sizeAttenuation: true,
      }));
      scene.add(particles);

      // ── Bursts ──
      const bCount = 60;
      const bPos = new Float32Array(bCount * 3);
      const bPhases = new Float32Array(bCount);
      const bRadii = new Float32Array(bCount);
      for (let i = 0; i < bCount; i++) {
        const a = Math.random() * Math.PI * 2;
        bRadii[i] = 0.5 + Math.random() * 2.4 * 0.8;
        bPos[i*3] = Math.cos(a) * bRadii[i];
        bPos[i*3+1] = Math.random() * 19;
        bPos[i*3+2] = Math.sin(a) * bRadii[i];
        bPhases[i] = Math.random() * Math.PI * 2;
      }
      const bGeo = new THREE.BufferGeometry();
      bGeo.setAttribute("position", new THREE.BufferAttribute(bPos, 3));
      bursts = new THREE.Points(bGeo, new THREE.PointsMaterial({
        color: 0xfbbf24, size: 0.06, transparent: true, opacity: 0.3,
        blending: THREE.AdditiveBlending, sizeAttenuation: true,
      }));
      scene.add(bursts);

      // ── Raycaster ──
      const raycaster = new THREE.Raycaster();
      const pointer = new THREE.Vector2();
      let hovered: any = null;

      canvas.addEventListener("pointermove", (e) => {
        const rect = canvas.getBoundingClientRect();
        pointer.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
        pointer.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
      });

      canvas.addEventListener("click", () => {
        if (hovered) {
          const d = hovered.userData;
          setInfo({
            title: `✦ ${d.tag} — ${d.milestone} (${d.rating}+)`,
            body: `Top programmers master "${d.tag}" at the ${d.milestone} level. This is a core skill in the progression pathway to ${d.rating}+ rating. Focus on solving problems tagged with "${d.tag}" at ${Math.max(d.rating - 200, 800)}–${d.rating + 200} difficulty.`,
          });
          setTimeout(() => setInfo(null), 5000);
        }
      });

      // ── Animation loop ──
      let time = 0;
      function animate() {
        if (!mounted) return;
        animId = requestAnimationFrame(animate);
        controls.update();
        time += 0.01;

        // Float particles
        if (particles) {
          const pos = particles.geometry.attributes.position.array;
          for (let i = 0; i < pCount; i++) {
            pos[i*3+1] += pVels[i].vy;
            if (pos[i*3+1] > 19) pos[i*3+1] = 0;
          }
          particles.geometry.attributes.position.needsUpdate = true;
        }

        // Animate bursts
        if (bursts) {
          const pos = bursts.geometry.attributes.position.array;
          const t = time;
          for (let i = 0; i < bCount; i++) {
            const phase = bPhases[i];
            const r = bRadii[i] * (0.8 + Math.sin(t * 0.5 + phase) * 0.2);
            pos[i*3] = Math.cos(t * 0.3 + phase) * r;
            pos[i*3+2] = Math.sin(t * 0.3 + phase) * r;
          }
          bursts.geometry.attributes.position.needsUpdate = true;
        }

        // Float tag spheres
        const t2 = time;
        tagSpheres.forEach((obj, i) => {
          const base = obj.userData._baseY ?? obj.position.y;
          obj.userData._baseY = obj.userData._baseY ?? obj.position.y;
          obj.position.y = base + Math.sin(t2 * 2 + i * 1.7) * 0.08;
          obj.rotation.y += 0.01;
        });

        // Hover detection
        raycaster.setFromCamera(pointer, camera);
        const intersects = raycaster.intersectObjects(tagSpheres);
        if (intersects.length > 0) {
          const obj = intersects[0].object;
          if (hovered !== obj) {
            if (hovered) { hovered.material.emissiveIntensity = 0.2; hovered.scale.set(1, 1, 1); }
            hovered = obj;
            hovered.material.emissiveIntensity = 0.8;
            hovered.scale.set(1.4, 1.4, 1.4);
            canvas.style.cursor = "pointer";
          }
        } else {
          if (hovered) {
            hovered.material.emissiveIntensity = 0.2;
            hovered.scale.set(1, 1, 1);
            hovered = null;
            canvas.style.cursor = "default";
          }
        }

        renderer.render(scene, camera);
        labelRenderer.render(scene, camera);
      }

      setLoading(false);
      animate();
    }

    init().catch((err) => {
      console.error("3D init error:", err);
      setLoading(false);
    });

    // ── Resize ──
    function onResize() {
      if (!canvas) return;
      const w = canvas.clientWidth;
      const h = canvas.clientHeight;
      if (camera) { camera.aspect = w / h; camera.updateProjectionMatrix(); }
      if (renderer) renderer.setSize(w, h);
      if (labelRenderer) labelRenderer.setSize(w, h);
    }
    window.addEventListener("resize", onResize);

    return () => {
      mounted = false;
      cancelAnimationFrame(animId);
      window.removeEventListener("resize", onResize);
      if (labelRenderer?.domElement?.parentNode) {
        labelRenderer.domElement.parentNode.removeChild(labelRenderer.domElement);
      }
      if (renderer) renderer.dispose();
    };
  }, []);

  return (
    <div className="fixed inset-0 bg-[#0a0e1a]">
      <canvas ref={canvasRef} className="w-full h-full block" />
      <HUD
        users={stats.users}
        subs={stats.subs}
        bt={stats.bt}
        loading={loading}
        info={info}
      />
    </div>
  );
}
