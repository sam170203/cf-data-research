from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.session import engine
from app.models.research import CollectionCheckpoint
from app.research.data_quality import DataQualityRunner
from app.research.pattern_discovery import PatternDiscoveryRunner
from app.research.hypothesis_gen import HypothesisGenerator
from app.research.hypothesis_test import HypothesisTester
from app.research.report_gen import ReportGenerator
from app.research.skill_vector import SkillVectorComputer

logger = logging.getLogger("research.coordinator")

LOOP_INTERVALS = {
    "data_acquisition": 300,
    "data_quality": 600,
    "pattern_discovery": 3600,
    "hypothesis_generation": 604800,  # Once per week — deprioritized
    "hypothesis_testing": 604800,  # Once per week — deprioritized
    "report_generation": 604800,  # Once per week — deprioritized
    "skill_vectors": 3600,
    "skill_graph": 7200,
}

CLUSTERING_INTERVAL = 7200
TRAJECTORY_INTERVAL = 3600
TRAJECTORY_TIMELINES_INTERVAL = 7200
EMBEDDING_INTERVAL = 7200


class ResearchCoordinator:
    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task[Any]] = {}
        self._running = False
        self._session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def get_all_status(self) -> dict[str, Any]:
        async with self._session_factory() as session:
            checkpoints = (
                await session.execute(select(CollectionCheckpoint))
            ).scalars().all()
        statuses = {cp.loop_name: {
            "status": cp.status,
            "total_processed": cp.total_processed,
            "last_handle": cp.last_handle,
            "updated_at": cp.updated_at.isoformat() if cp.updated_at else None,
        } for cp in checkpoints}
        for loop in LOOP_INTERVALS:
            if loop not in statuses:
                statuses[loop] = {"status": "pending", "total_processed": 0}
        return statuses

    async def _upsert_checkpoint(
        self, session: AsyncSession, loop_name: str, **kwargs: Any
    ) -> CollectionCheckpoint:
        result = await session.execute(
            select(CollectionCheckpoint).where(
                CollectionCheckpoint.loop_name == loop_name
            )
        )
        cp = result.scalar_one_or_none()
        if cp is None:
            cp = CollectionCheckpoint(loop_name=loop_name, **kwargs)
            session.add(cp)
        else:
            for k, v in kwargs.items():
                setattr(cp, k, v)
            cp.updated_at = datetime.now(UTC)
        await session.commit()
        return cp

    async def start(self) -> None:
        if self._running:
            logger.warning("Coordinator already running")
            return
        self._running = True
        self._tasks["data_acquisition"] = asyncio.create_task(
            self._loop_data_acquisition()
        )
        self._tasks["data_quality"] = asyncio.create_task(
            self._loop_data_quality()
        )
        self._tasks["pattern_discovery"] = asyncio.create_task(
            self._loop_pattern_discovery()
        )
        self._tasks["hypothesis_generation"] = asyncio.create_task(
            self._loop_hypothesis_generation()
        )
        self._tasks["hypothesis_testing"] = asyncio.create_task(
            self._loop_hypothesis_testing()
        )
        self._tasks["report_generation"] = asyncio.create_task(
            self._loop_report_generation()
        )
        self._tasks["skill_vectors"] = asyncio.create_task(
            self._loop_skill_vectors()
        )
        self._tasks["skill_graph"] = asyncio.create_task(
            self._loop_skill_graph()
        )
        self._tasks["embeddings"] = asyncio.create_task(
            self._loop_embeddings()
        )
        self._tasks["clustering"] = asyncio.create_task(
            self._loop_clustering()
        )
        self._tasks["trajectories"] = asyncio.create_task(
            self._loop_trajectories()
        )
        self._tasks["trajectory_timelines"] = asyncio.create_task(
            self._loop_trajectory_timelines()
        )
        logger.info("Research coordinator started with all 12 loops")

    async def stop(self) -> None:
        self._running = False
        for name, task in self._tasks.items():
            task.cancel()
        await asyncio.gather(*self._tasks.values(), return_exceptions=True)
        self._tasks.clear()
        logger.info("Research coordinator stopped")

    async def run_once(self, loop_name: str) -> dict[str, Any]:
        runners = {
            "data_acquisition": self._run_acquisition,
            "data_quality": self._run_quality,
            "pattern_discovery": self._run_pattern_discovery,
            "hypothesis_generation": self._run_hypothesis_generation,
            "hypothesis_testing": self._run_hypothesis_testing,
            "report_generation": self._run_report_generation,
            "skill_vectors": self._run_skill_vectors,
            "skill_graph": self._run_skill_graph,
            "prediction": self._run_prediction,
            "failure_analysis": self._run_failure_analysis,
            "embeddings": self._run_embeddings,
            "clustering": self._run_clustering,
            "trajectories": self._run_trajectories,
            "trajectory_timelines": self._run_trajectory_timelines,
        }
        runner = runners.get(loop_name)
        if not runner:
            return {"error": f"Unknown loop: {loop_name}"}
        return await runner()

    async def _loop_data_acquisition(self) -> None:
        while self._running:
            try:
                await self._run_acquisition()
            except Exception as e:
                logger.exception("Data acquisition loop error: %s", e)
            await asyncio.sleep(LOOP_INTERVALS["data_acquisition"])

    async def _run_acquisition(self) -> dict[str, Any]:
        async with self._session_factory() as session:
            cp = (
                await session.execute(
                    select(CollectionCheckpoint).where(
                        CollectionCheckpoint.loop_name == "data_acquisition"
                    )
                )
            ).scalar_one_or_none()

        from app.models.user import User
        from sqlalchemy import func

        async with self._session_factory() as session:
            user_count = (
                await session.execute(select(func.count()).select_from(User))
            ).scalar_one() or 0

        target = 1000
        if user_count >= target:
            await self._upsert_checkpoint_async("data_acquisition",
                                                total_processed=user_count, status="complete")
            return {"status": "complete", "total": user_count}

        batch_size = 25
        remaining = target - user_count
        count = min(batch_size, remaining)

        logger.info("Acquisition: collecting %d users (have %d, need %d)", count, user_count, target)
        await self._collect_users_batch(count)

        async with self._session_factory() as session:
            user_count = (
                await session.execute(select(func.count()).select_from(User))
            ).scalar_one() or 0
            status = "complete" if user_count >= target else "running"
            await self._upsert_checkpoint_async(
                "data_acquisition", total_processed=user_count, status=status,
            )
        return {"status": status, "total": user_count}

    async def _collect_users_batch(self, count: int) -> None:
        from app.models.user import User
        from app.services.codeforces import CodeforcesClient, CodeforcesAPIError
        from scrapers.codeforces.ingest import ingest_all_user_data

        client = CodeforcesClient()

        try:
            async with self._session_factory() as session:
                existing_handles = set(
                    (await session.execute(select(User.cf_handle))).scalars().all()
                )
            existing_count = len(existing_handles)

            # Fetch rated list with offset to skip already-collected users
            top_handles = await self._fetch_top_handles(client, count + existing_count * 2)
            new_handles = [h for h in top_handles if h not in existing_handles]

            # Add historic legends that aren't already collected
            historic = [
                "tourist", "Petr", "rng_58", "Egor", "ACRush", "pajenegod",
                "aryan", "orz", "hos.lyric", "dzhulgakov", "vepifanov",
                "JOHNKRAM", "Burunduk1", "eatmore", "scott_wu", "ecnerwala",
                "tmwilliamlin", "Errichto", "SecondThread",
            ]
            for h in historic:
                if h not in existing_handles and h not in new_handles:
                    new_handles.append(h)

            new_handles = new_handles[:count]

            if not new_handles:
                logger.warning("No new users to collect (existing=%d, top_fetched=%d)",
                               existing_count, len(top_handles))
                return

            logger.info("Collecting %d new users (existing=%d)", len(new_handles), existing_count)

            for idx, handle in enumerate(new_handles, 1):
                try:
                    async with self._session_factory() as session:
                        result = await ingest_all_user_data(client, session, handle)
                        status = result.get("status", "failed")
                        if status == "success":
                            logger.info("[%d/%d] %s ✓ (%d subs, %d contests)",
                                        idx, len(new_handles), handle,
                                        result.get("submissions_count", 0),
                                        result.get("rating_histories_count", 0))
                        else:
                            logger.warning("[%d/%d] %s ✗ (%s)",
                                          idx, len(new_handles), handle, result.get("reason"))
                except Exception as e:
                    logger.warning("Failed to collect %s: %s", handle, e)

        finally:
            await client.close()

    async def _fetch_top_handles(self, client: CodeforcesClient, count: int) -> list[str]:
        try:
            result = await client._request(
                "GET", "/user.ratedList",
                params={"activeOnly": "true", "includeRetired": "false"},
            )
            if isinstance(result, list):
                handles = []
                for u in result:
                    h = u.get("handle")
                    if h:
                        handles.append(h)
                        if len(handles) >= count:
                            break
                return handles
        except Exception as e:
            logger.warning("Failed to fetch top handles: %s", e)
        return []

    async def _upsert_checkpoint_async(self, loop_name: str, **kwargs: Any) -> None:
        async with self._session_factory() as session:
            await self._upsert_checkpoint(session, loop_name, **kwargs)

    async def _loop_data_quality(self) -> None:
        while self._running:
            try:
                await self._run_quality()
            except Exception as e:
                logger.exception("Data quality loop error: %s", e)
            await asyncio.sleep(LOOP_INTERVALS["data_quality"])

    async def _run_quality(self) -> dict[str, Any]:
        runner = DataQualityRunner(self._session_factory)
        report = await runner.run()
        async with self._session_factory() as session:
            await self._upsert_checkpoint(
                session, "data_quality", total_processed=1, status="complete"
            )
        return report

    async def _loop_pattern_discovery(self) -> None:
        while self._running:
            try:
                await self._run_pattern_discovery()
            except Exception as e:
                logger.exception("Pattern discovery loop error: %s", e)
            await asyncio.sleep(LOOP_INTERVALS["pattern_discovery"])

    async def _run_pattern_discovery(self) -> dict[str, Any]:
        runner = PatternDiscoveryRunner(self._session_factory)
        findings = await runner.run()
        async with self._session_factory() as session:
            await self._upsert_checkpoint(
                session, "pattern_discovery", total_processed=len(findings), status="complete"
            )
        return {"findings_count": len(findings)}

    async def _loop_hypothesis_generation(self) -> None:
        while self._running:
            try:
                await self._run_hypothesis_generation()
            except Exception as e:
                logger.exception("Hypothesis generation loop error: %s", e)
            await asyncio.sleep(LOOP_INTERVALS["hypothesis_generation"])

    async def _run_hypothesis_generation(self) -> dict[str, Any]:
        gen = HypothesisGenerator(self._session_factory)
        count = await gen.run()
        async with self._session_factory() as session:
            await self._upsert_checkpoint(
                session, "hypothesis_generation", total_processed=count, status="complete"
            )
        return {"hypotheses_generated": count}

    async def _loop_hypothesis_testing(self) -> None:
        while self._running:
            try:
                await self._run_hypothesis_testing()
            except Exception as e:
                logger.exception("Hypothesis testing loop error: %s", e)
            await asyncio.sleep(LOOP_INTERVALS["hypothesis_testing"])

    async def _run_hypothesis_testing(self) -> dict[str, Any]:
        tester = HypothesisTester(self._session_factory)
        results = await tester.run()
        async with self._session_factory() as session:
            await self._upsert_checkpoint(
                session, "hypothesis_testing", total_processed=len(results), status="complete"
            )
        return {"tested": len(results)}

    async def _loop_report_generation(self) -> None:
        while self._running:
            try:
                await self._run_report_generation()
            except Exception as e:
                logger.exception("Report generation loop error: %s", e)
            await asyncio.sleep(LOOP_INTERVALS["report_generation"])

    async def _run_report_generation(self) -> dict[str, Any]:
        gen = ReportGenerator(self._session_factory)
        report = await gen.run()
        async with self._session_factory() as session:
            await self._upsert_checkpoint(
                session, "report_generation", total_processed=1, status="complete"
            )
        return {"report_id": report.get("id")}

    async def _loop_skill_vectors(self) -> None:
        while self._running:
            try:
                await self._run_skill_vectors()
            except Exception as e:
                logger.exception("Skill vector loop error: %s", e)
            await asyncio.sleep(LOOP_INTERVALS["skill_vectors"])

    async def _run_skill_vectors(self) -> dict[str, Any]:
        computer = SkillVectorComputer(self._session_factory)
        count = await computer.run()
        async with self._session_factory() as session:
            await self._upsert_checkpoint(
                session, "skill_vectors", total_processed=count, status="complete"
            )
        return {"users_computed": count}

    async def _loop_skill_graph(self) -> None:
        while self._running:
            try:
                await self._run_skill_graph()
            except Exception as e:
                logger.exception("Skill graph loop error: %s", e)
            await asyncio.sleep(LOOP_INTERVALS["skill_graph"])

    async def _run_skill_graph(self) -> dict[str, Any]:
        from app.research.skill_graph import SkillGraphBuilder
        builder = SkillGraphBuilder(self._session_factory)
        result = await builder.run()
        async with self._session_factory() as session:
            await self._upsert_checkpoint(
                session, "skill_graph",
                total_processed=result.get("strong_edges", 0),
                status="complete",
            )
        return result

    async def _loop_embeddings(self) -> None:
        while self._running:
            try:
                await self._run_embeddings()
            except Exception as e:
                logger.exception("Embeddings loop error: %s", e)
            await asyncio.sleep(EMBEDDING_INTERVAL)

    async def _run_embeddings(self) -> dict[str, Any]:
        from app.research.embeddings import UserEmbeddingComputer
        computer = UserEmbeddingComputer(self._session_factory)
        count = await computer.compute_all()
        async with self._session_factory() as session:
            await self._upsert_checkpoint(
                session, "embeddings", total_processed=count, status="complete"
            )
        return {"users_embedded": count}

    async def _loop_clustering(self) -> None:
        while self._running:
            try:
                await self._run_clustering()
            except Exception as e:
                logger.exception("Clustering loop error: %s", e)
            await asyncio.sleep(CLUSTERING_INTERVAL)

    async def _run_clustering(self) -> dict[str, Any]:
        from app.research.clustering import ClusteringEngine
        engine = ClusteringEngine(self._session_factory)
        results = await engine.run_all()
        async with self._session_factory() as session:
            await self._upsert_checkpoint(
                session, "clustering",
                total_processed=results.get("n_users", 0),
                status="complete",
            )
        return results

    async def _loop_trajectories(self) -> None:
        while self._running:
            try:
                await self._run_trajectories()
            except Exception as e:
                logger.exception("Trajectories loop error: %s", e)
            await asyncio.sleep(TRAJECTORY_INTERVAL)

    async def _run_trajectories(self) -> dict[str, Any]:
        from app.research.trajectories import TrajectoryAnalyzer
        analyzer = TrajectoryAnalyzer(self._session_factory)
        results = await analyzer.discover_all()
        async with self._session_factory() as session:
            total = sum(len(v.get("users", [])) for v in results.values() if isinstance(v, dict))
            await self._upsert_checkpoint(
                session, "trajectories", total_processed=total, status="complete"
            )
        return results

    async def _run_trajectory_timelines(self) -> dict[str, Any]:
        from app.research.trajectory_timelines import (
            TrajectoryTimelineBuilder, TrajectoryQuestionAnswerer,
        )
        builder = TrajectoryTimelineBuilder(self._session_factory)
        timelines = await builder.build_all_timelines()
        answerer = TrajectoryQuestionAnswerer(timelines)
        results = answerer.run_all()
        logger.info("Trajectory timelines: %d users", len(timelines))
        return results

    async def _run_prediction(self) -> dict[str, Any]:
        from app.research.predictor import Predictor
        predictor = Predictor(self._session_factory)
        results = await predictor.run_full_pipeline()

        async with self._session_factory() as session:
            for task_type in ["classification", "regression"]:
                tasks = results.get(task_type, {})
                for task_name, task_result in tasks.items():
                    if "error" in task_result:
                        continue
                    best_model = task_result.get("best_model", "")
                    best_metrics = task_result.get(best_model, {})
                    from app.models.research import PredictionRun, ExperimentTracking
                    pr = PredictionRun(
                        task_type=task_type,
                        task_name=task_name,
                        model_type=best_model,
                        accuracy=best_metrics.get("accuracy"),
                        f1_score=best_metrics.get("f1"),
                        roc_auc=best_metrics.get("roc_auc"),
                        mae=best_metrics.get("mae"),
                        rmse=best_metrics.get("rmse"),
                        r2=best_metrics.get("r2"),
                        feature_importance={"features": task_result.get("feature_importance", [])},
                        shap_values={"features": task_result.get("shap_values", [])},
                        sample_size=best_metrics.get("test_size", 0),
                    )
                    session.add(pr)
                    session.add(ExperimentTracking(
                        run_name=f"baseline_{task_name}_{best_model}",
                        dataset_version="v1",
                        feature_version="v1",
                        model_type=best_model,
                        task_name=task_name,
                        task_type=task_type,
                        metrics=best_metrics,
                        feature_importance={"features": task_result.get("feature_importance", [])},
                        sample_size=best_metrics.get("test_size", 0),
                    ))
            await session.commit()

        summary = predictor.get_model_summary(results)
        logger.info("Prediction complete:\n%s", summary)
        return {"status": "complete", "results": results}

    async def _run_failure_analysis(self) -> dict[str, Any]:
        from app.research.features import FeatureComputer
        from app.research.failure_analysis import FailureAnalyzer
        from app.research.predictor import Predictor, ALL_FEATURES, CLASSIFICATION_TASKS

        df = await FeatureComputer(self._session_factory).build_feature_matrix(include_labels=True)

        analyzer = FailureAnalyzer(self._session_factory)
        results = {}
        for task_name, config in CLASSIFICATION_TASKS.items():
            valid = df[df[config["target"]] >= 0]
            if len(valid) < 10:
                continue
            X = valid[ALL_FEATURES].fillna(0)
            y = valid[config["target"]].astype(int)
            if y.nunique() < 2:
                continue
            from sklearn.model_selection import train_test_split
            from sklearn.linear_model import LogisticRegression
            from sklearn.preprocessing import StandardScaler
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.3, random_state=42, stratify=y,
            )
            scaler = StandardScaler()
            X_train_s = scaler.fit_transform(X_train)
            X_test_s = scaler.transform(X_test)
            model = LogisticRegression(max_iter=2000, class_weight="balanced", random_state=42)
            model.fit(X_train_s, y_train)
            test_idx = X_test.index
            test_df = valid.loc[test_idx]
            analysis = await analyzer.analyze(
                test_df, task_name, model, config["target"],
                X=X_test_s, y_true=y_test,
            )
            results[task_name] = analysis

            for hyp in analysis.get("hypotheses", []):
                from app.models.research import ResearchHypothesis
                async with self._session_factory() as session:
                    existing = await session.execute(
                        select(ResearchHypothesis).where(
                            ResearchHypothesis.question == hyp
                        )
                    )
                    if not existing.scalar_one_or_none():
                        session.add(ResearchHypothesis(
                            question=hyp,
                            priority=8,
                            category="failure_analysis",
                            status="generated",
                        ))
                        await session.commit()

        logger.info("Failure analysis: %d tasks analyzed", len(results))
        return {"status": "complete", "tasks": len(results)}

    async def _loop_trajectory_timelines(self) -> None:
        """Compute per-user trajectory timelines every TRAJECTORY_TIMELINES_INTERVAL."""
        while self._running:
            try:
                from app.research.trajectory_timelines import (
                    TrajectoryTimelineBuilder, TrajectoryQuestionAnswerer,
                )
                builder = TrajectoryTimelineBuilder(self._session_factory)
                timelines = await builder.build_all_timelines()
                answerer = TrajectoryQuestionAnswerer(timelines)
                results = answerer.run_all()
                logger.info(
                    "Trajectory timelines: %d users, %d breakthrough events",
                    len(timelines),
                    results.get("q2_before_breakthrough", {}).get("breakthrough_events", 0),
                )
            except Exception as e:
                logger.error("Trajectory timelines loop failed: %s", e)
            await asyncio.sleep(TRAJECTORY_TIMELINES_INTERVAL)
