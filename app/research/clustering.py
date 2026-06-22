from __future__ import annotations

import logging
import uuid
from collections import Counter
from typing import Any

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans, AgglomerativeClustering
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.research import UserEmbedding, UserCluster
from app.models.user import User

try:
    import hdbscan
    HAS_HDBSCAN = True
except ImportError:
    HAS_HDBSCAN = False

logger = logging.getLogger("research.clustering")

def _derive_archetype_name(cluster_info: dict[str, Any]) -> str:
    """Assign meaningful archetype name based on cluster characteristics."""
    rating = cluster_info.get("avg_rating", 0)
    growth = cluster_info.get("avg_growth_velocity", 0)
    accel = cluster_info.get("avg_growth_acceleration", 0)
    contests = cluster_info.get("avg_contests", 0)
    solved = cluster_info.get("avg_solved", 0)
    diversity = cluster_info.get("avg_tag_diversity", 0)
    volatility = cluster_info.get("avg_volatility", 0)
    subs_per_day = cluster_info.get("avg_submissions_per_day", 0)
    inactivity = cluster_info.get("avg_inactivity_streak", 0)

    # Detect outliers / special cases first
    if solved == 0 and subs_per_day == 0:
        return "Inactive"

    # High-growth clusters (rapid improvers)
    if growth > 80 and contests < 15:
        return "Fast Risers"
    if growth > 30:
        return "Rapid Improvers"

    # Dedicated practice grinders
    if subs_per_day > 1.0 and solved > 800:
        if diversity > 15:
            return "Diverse Practice Grinders"
        return "Practice Grinders"

    # Heavy contest participants
    if contests > 100:
        if rating > 2600:
            return "Veteran Elites"
        return "Contest Veterans"

    # High-volume solvers
    if solved > 1500:
        if growth > 0:
            return "Active High-Volume"
        return "High-Volume Solvers"

    # Growth-based differentiation for moderate users
    if growth > 10:
        if diversity > 12:
            return "Growing Generalists"
        return "Steady Improvers"
    if growth > 0:
        if contests > 40:
            return "Consistent Contestants"
        return "Slow Improvers"
    if growth < -10:
        return "Declining"

    # By practice patterns
    if contests > 50:
        return "Contest Regulars"
    if subs_per_day > 0.5:
        return "Regular Practitioners"

    # Fallbacks by rating band
    if rating > 2400:
        return "Established Elite"
    if rating > 2000:
        return "Established Experts"
    return "Developing Participants"


CLUSTER_ARCHETYPES: dict[int, str] = {}


class ClusteringEngine:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def run_all(self) -> dict[str, Any]:
        embeddings = await self._load_embeddings()
        if len(embeddings) < 10:
            return {"error": f"Too few embeddings ({len(embeddings)})"}

        df = pd.DataFrame(embeddings)
        feature_cols = [c for c in df.columns if c not in ("user_id", "handle", "current_rating", "max_rating")]
        X = df[feature_cols].fillna(0).values
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        results: dict[str, Any] = {"n_users": len(df), "runs": []}

        runs = []

        km = await self._run_kmeans(X_scaled, df)
        if km:
            runs.append(km)

        hdb = await self._run_hdbscan(X_scaled, df)
        if hdb:
            runs.append(hdb)

        hc = await self._run_hierarchical(X_scaled, df)
        if hc:
            runs.append(hc)

        results["runs"] = runs
        logger.info("Clustering complete: %d algorithms, %d users", len(runs), len(df))
        return results

    async def _load_embeddings(self) -> list[dict[str, Any]]:
        async with self._sf() as session:
            rows = (
                await session.execute(
                    select(UserEmbedding).order_by(UserEmbedding.user_id)
                )
            ).scalars().all()

        result = []
        for r in rows:
            emb = dict(r.embedding)
            emb["user_id"] = r.user_id
            emb["handle"] = r.handle
            emb["current_rating"] = r.current_rating
            emb["max_rating"] = r.max_rating
            result.append(emb)
        return result

    async def _run_kmeans(self, X: np.ndarray, df: pd.DataFrame) -> dict[str, Any] | None:
        n = min(10, max(3, len(X) // 20))
        try:
            model = KMeans(n_clusters=n, random_state=42, n_init="auto")
            labels = model.fit_predict(X)
            sil = silhouette_score(X, labels) if len(set(labels)) > 1 else 0.0

            cluster_info = self._build_cluster_info(labels, df, X)
            await self._store_run("kmeans", n, sil, cluster_info)

            await self._assign_cluster_labels(labels, cluster_info, df)

            return {
                "algorithm": "kmeans",
                "n_clusters": n,
                "silhouette": round(float(sil), 4),
                "clusters": cluster_info,
            }
        except Exception as e:
            logger.warning("KMeans failed: %s", e)
            return None

    async def _run_hdbscan(self, X: np.ndarray, df: pd.DataFrame) -> dict[str, Any] | None:
        if not HAS_HDBSCAN:
            logger.info("HDBSCAN not installed, skipping")
            return None
        try:
            model = hdbscan.HDBSCAN(min_cluster_size=max(3, len(X) // 50), min_samples=1)
            labels = model.fit_predict(X)
            n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
            sil = silhouette_score(X, labels) if n_clusters > 1 else 0.0

            cluster_info = self._build_cluster_info(labels, df, X)
            await self._store_run("hdbscan", n_clusters, sil, cluster_info)

            return {
                "algorithm": "hdbscan",
                "n_clusters": n_clusters,
                "noise_points": int((labels == -1).sum()),
                "silhouette": round(float(sil), 4),
                "clusters": cluster_info,
            }
        except Exception as e:
            logger.warning("HDBSCAN failed: %s", e)
            return None

    async def _run_hierarchical(self, X: np.ndarray, df: pd.DataFrame) -> dict[str, Any] | None:
        n = min(10, max(3, len(X) // 20))
        try:
            model = AgglomerativeClustering(n_clusters=n, linkage="ward")
            labels = model.fit_predict(X)
            sil = silhouette_score(X, labels) if len(set(labels)) > 1 else 0.0

            cluster_info = self._build_cluster_info(labels, df, X)
            await self._store_run("hierarchical", n, sil, cluster_info)

            return {
                "algorithm": "hierarchical",
                "n_clusters": n,
                "silhouette": round(float(sil), 4),
                "clusters": cluster_info,
            }
        except Exception as e:
            logger.warning("Hierarchical failed: %s", e)
            return None

    def _build_cluster_info(self, labels: np.ndarray, df: pd.DataFrame, X: np.ndarray) -> list[dict[str, Any]]:
        unique_labels = sorted(set(l for l in labels if l >= 0))
        info = []
        for label in unique_labels:
            mask = labels == label
            cluster_df = df[mask]
            cluster_X = X[mask]
            n_users = len(cluster_df)

            avg_rating = float(cluster_df["current_rating"].mean())
            avg_max_rating = float(cluster_df["max_rating"].mean())
            avg_growth_velocity = float(cluster_df.get("growth_velocity", pd.Series([0])).mean())
            avg_growth_accel = float(cluster_df.get("growth_acceleration", pd.Series([0])).mean())
            avg_contests = float(cluster_df.get("total_contests", pd.Series([0])).mean())
            avg_solved = float(cluster_df.get("total_solved", pd.Series([0])).mean())
            avg_tag_diversity = float(cluster_df.get("tag_diversity", pd.Series([0])).mean())
            avg_volatility = float(cluster_df.get("rating_volatility", pd.Series([0])).mean())
            avg_sub_per_day = float(cluster_df.get("submissions_per_day", pd.Series([0])).mean())
            avg_inactivity = float(cluster_df.get("max_inactivity_streak", pd.Series([0])).mean())

            tag_cols = [c for c in cluster_df.columns if c.startswith("tag_")]
            if tag_cols:
                tag_means = cluster_df[tag_cols].mean().sort_values(ascending=False)
                dominant_tags = tag_means.head(5).to_dict()
            else:
                dominant_tags = {}

            entry = {
                "label": int(label),
                "n_users": n_users,
                "avg_rating": round(avg_rating, 1),
                "avg_max_rating": round(avg_max_rating, 1),
                "avg_growth_velocity": round(avg_growth_velocity, 2),
                "avg_growth_acceleration": round(avg_growth_accel, 2),
                "avg_contests": round(avg_contests, 1),
                "avg_solved": round(avg_solved, 1),
                "avg_tag_diversity": round(avg_tag_diversity, 1),
                "avg_volatility": round(avg_volatility, 2),
                "avg_submissions_per_day": round(avg_sub_per_day, 3),
                "avg_inactivity_streak": round(avg_inactivity, 1),
                "dominant_tags": dominant_tags,
                "handles": cluster_df["handle"].tolist()[:20],
            }
            entry["name"] = _derive_archetype_name(entry)
            info.append(entry)
        return info

    async def _store_run(self, algorithm: str, n_clusters: int, sil: float, cluster_info: list) -> None:
        run_id = uuid.uuid4().hex[:8]
        async with self._sf() as session:
            session.add(UserCluster(
                run_id=run_id,
                algorithm=algorithm,
                n_clusters=n_clusters,
                metric="silhouette",
                metric_value=round(float(sil), 4),
                clusters={"clusters": cluster_info},
            ))
            await session.commit()
        logger.info("Stored %s clustering run %s (sil=%.3f)", algorithm, run_id, sil)

    async def _assign_cluster_labels(self, labels: np.ndarray, cluster_info: list, df: pd.DataFrame) -> None:
        label_to_name = {c["label"]: c["name"] for c in cluster_info}
        uids = [int(row["user_id"]) for _, row in df.iterrows()]
        async with self._sf() as session:
            for i, uid in enumerate(uids):
                label = int(labels[i])
                if label < 0:
                    continue
                name = label_to_name.get(label, f"Cluster {label}")
                emb = await session.execute(
                    select(UserEmbedding).where(UserEmbedding.user_id == uid)
                )
                emb = emb.scalar_one_or_none()
                if emb:
                    emb.cluster_label = label
                    emb.cluster_name = name
                    if (i + 1) % 50 == 0:
                        await session.flush()
            await session.commit()
