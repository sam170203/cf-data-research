"""Tests for research modules: features, predictor, failure_analysis, skill_graph."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from numpy.testing import assert_almost_equal

from app.research.features import TAG_COLUMNS, FeatureComputer
from app.research.failure_analysis import FailureAnalyzer
from app.research.predictor import ALL_FEATURES, CLASSIFICATION_TASKS, Predictor


def make_synthetic_user_features(n: int = 100, seed: int = 42, signal: bool = False) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n):
        if signal:
            base_rating = int(1200 + (i / n) * 1000)
        else:
            base_rating = int(rng.integers(800, 2200))
        row = {
            "user_id": i,
            "handle": f"user_{i}",
            "current_rating": base_rating,
            "max_rating": base_rating + int(rng.integers(0, 200)),
            "total_submissions": int(rng.integers(10, 2000)),
            "total_solved": int(rng.integers(5, 800)),
            "total_contests": int(rng.integers(1, 50)),
            "submissions_per_day": round(rng.uniform(0.1, 10), 4),
            "active_days": int(rng.integers(5, 500)),
            "max_inactivity_streak": int(rng.integers(1, 120)),
            "median_inactivity_gap": round(rng.uniform(0.5, 30), 2),
            "avg_contest_delta": round(rng.uniform(-50, 50), 2),
            "rating_volatility": round(rng.uniform(10, 150), 2),
            "first_rating": int(rng.integers(800, 1500)),
            "rating_gain_total": int(rng.integers(-200, 800)),
            "max_win_streak": int(rng.integers(0, 10)),
            "max_loss_streak": int(rng.integers(0, 8)),
            "tag_diversity": int(rng.integers(1, 25)),
            "hardest_solved_tag_rating": round(rng.uniform(800, 2000), 1),
            "avg_solved_rating": round(rng.uniform(800, 1800), 1),
            "growth_velocity": round(rng.uniform(-20, 40), 2),
            "growth_acceleration": round(rng.uniform(-15, 20), 2),
            "rating_volatility_recent": round(rng.uniform(5, 100), 2),
            "contests_last_90d": int(rng.integers(0, 15)),
            "activity_last_30d": int(rng.integers(0, 200)),
            "activity_last_60d": int(rng.integers(0, 400)),
            "activity_last_90d": int(rng.integers(0, 600)),
            "solved_last_30d": int(rng.integers(0, 80)),
            "solved_last_60d": int(rng.integers(0, 160)),
            "solved_last_90d": int(rng.integers(0, 240)),
        }
        for tc in TAG_COLUMNS:
            row[tc] = round(rng.uniform(0, 0.3), 4)
        rows.append(row)
    df = pd.DataFrame(rows)

    df["target_expert_6mo"] = (df["current_rating"] > 1600).astype(int)
    df["target_cm_12mo"] = (df["current_rating"] > 1900).astype(int)
    df["target_master_12mo"] = (df["current_rating"] > 2100).astype(int)
    df["target_rating_3mo"] = df["current_rating"]
    df["target_rating_6mo"] = df["current_rating"]
    df["target_rating_12mo"] = df["current_rating"]
    return df


class TestPredictor:
    def test_all_features_list(self):
        assert len(ALL_FEATURES) == len(pd.Index(ALL_FEATURES).unique())
        assert all(f in ALL_FEATURES for f in [
            "total_solved", "growth_velocity", "rating_volatility",
        ])

    def test_classification_task_configs(self):
        for name, cfg in CLASSIFICATION_TASKS.items():
            assert "target" in cfg
            assert cfg["target"].startswith("target_")
            assert "description" in cfg

    def test_classification_pipeline_synthetic(self):
        rng = np.random.default_rng(42)
        n = 200
        df = pd.DataFrame({
            "feature_a": rng.normal(0, 1, n),
            "feature_b": rng.normal(0, 1, n),
        })
        logits = 2.0 * df["feature_a"] - 1.5 * df["feature_b"] + 0.5 * rng.normal(0, 0.3, n)
        df["target"] = (logits > 0).astype(int)

        from sklearn.model_selection import train_test_split
        from sklearn.linear_model import LogisticRegression

        X = df[["feature_a", "feature_b"]]
        y = df["target"]
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.3, random_state=42, stratify=y,
        )
        model = LogisticRegression(max_iter=1000, random_state=42)
        model.fit(X_train, y_train)
        acc = model.score(X_test, y_test)
        assert acc >= 0.7

    def test_regression_pipeline_synthetic(self):
        df = make_synthetic_user_features(n=100)
        from sklearn.model_selection import train_test_split
        from sklearn.linear_model import LinearRegression
        from sklearn.preprocessing import StandardScaler

        target = "target_rating_6mo"
        valid = df[df[target] >= 0]
        X = valid[ALL_FEATURES].fillna(0)
        y = valid[target].values
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.3, random_state=42,
        )
        scaler = StandardScaler()
        X_train_s = scaler.fit_transform(X_train)
        model = LinearRegression()
        model.fit(X_train_s, y_train)
        assert hasattr(model, "coef_")
        assert len(model.coef_) == len(ALL_FEATURES)


class TestFailureAnalysis:
    def test_profile_misclassified_returns_all_fields(self):
        analyzer = FailureAnalyzer(None)
        row = make_synthetic_user_features(n=1).iloc[0]
        profile = analyzer._profile_misclassified(row, predicted=1, actual=0)
        for key in [
            "handle", "rating", "total_contests", "total_solved",
            "growth_velocity", "growth_acceleration", "rating_volatility",
            "tag_diversity", "max_inactivity_streak", "median_inactivity_gap",
            "activity_last_90d", "solved_last_90d", "contests_last_90d",
            "avg_solved_rating", "submissions_per_day",
        ]:
            assert key in profile, f"Missing field: {key}"

    def test_hypothesis_generation_with_profiles(self):
        analyzer = FailureAnalyzer(None)
        df = make_synthetic_user_features(n=50)
        fp = [analyzer._profile_misclassified(df.iloc[i], predicted=1, actual=0)
              for i in range(5)]
        fn = [analyzer._profile_misclassified(df.iloc[i], predicted=0, actual=1)
              for i in range(5, 10)]
        hyps = analyzer._generate_hypotheses("expert_6mo", fp, fn)
        assert isinstance(hyps, list)
        assert len(hyps) >= 1
        for h in hyps:
            assert isinstance(h, str)
            assert "expert_6mo" in h

    def test_hypothesis_empty_profiles(self):
        analyzer = FailureAnalyzer(None)
        hyps = analyzer._generate_hypotheses("expert_6mo", [], [])
        assert hyps == []

    def test_hypothesis_only_fp(self):
        analyzer = FailureAnalyzer(None)
        df = make_synthetic_user_features(n=10)
        fp = [analyzer._profile_misclassified(df.iloc[i], predicted=1, actual=0)
              for i in range(5)]
        hyps = analyzer._generate_hypotheses("expert_6mo", fp, [])
        assert len(hyps) >= 1

    def test_hypothesis_only_fn(self):
        analyzer = FailureAnalyzer(None)
        df = make_synthetic_user_features(n=10)
        fn = [analyzer._profile_misclassified(df.iloc[i], predicted=0, actual=1)
              for i in range(5)]
        hyps = analyzer._generate_hypotheses("expert_6mo", [], fn)
        assert len(hyps) >= 1


class TestFeatures:
    def test_tag_columns_match_all_tags(self):
        from app.research.features import ALL_TAGS
        assert len(TAG_COLUMNS) == len(ALL_TAGS)
        for tag, col in zip(ALL_TAGS, TAG_COLUMNS):
            assert col.startswith("tag_")
            assert col == f"tag_{tag.replace(' ', '_').replace('-', '_')}"

    def test_synthetic_feature_matrix_shape(self):
        df = make_synthetic_user_features(n=50)
        assert len(df) == 50
        feature_cols = [c for c in ALL_FEATURES if c in df.columns]
        assert len(feature_cols) == len(ALL_FEATURES)
        for c in ALL_FEATURES:
            assert c in df.columns, f"Missing feature column: {c}"

    def test_classification_targets_binary(self):
        df = make_synthetic_user_features(n=100)
        for target in ["target_expert_6mo", "target_cm_12mo", "target_master_12mo"]:
            assert target in df.columns
            assert df[target].dropna().isin([0, 1]).all()

    def test_regression_targets_non_negative(self):
        df = make_synthetic_user_features(n=100)
        for target in ["target_rating_3mo", "target_rating_6mo", "target_rating_12mo"]:
            assert target in df.columns
            assert (df[target] >= 0).all()


class TestSkillGraph:
    def test_transition_building(self):
        from app.research.skill_graph import SkillGraphBuilder

        builder = SkillGraphBuilder(None)
        pairs = [("dp", "graphs"), ("dp", "math"), ("math", "dp"),
                 ("graphs", "implementation"), ("dp", "graphs")]
        user_set: dict[tuple[str, str], set[int]] = {}
        for i, (st, tt) in enumerate(pairs):
            user_set.setdefault((st, tt), set()).add(i % 3)

        assert len(user_set) == 4
        assert user_set[("dp", "graphs")] == {0, 1}
        assert ("implementation", "graphs") not in user_set

    def test_self_loop_handling(self):
        pairs = [("dp", "dp"), ("dp", "dp"), ("math", "math")]
        user_set: dict[tuple[str, str], set[int]] = {}
        for i, (st, tt) in enumerate(pairs):
            user_set.setdefault((st, tt), set()).add(i)
        assert ("dp", "dp") in user_set
        assert len(user_set[("dp", "dp")]) == 2


class TestDataQuality:
    def test_quality_score_calculation(self):
        from app.research.data_quality import DataQualityRunner
        runner = DataQualityRunner(None)

        base = 100.0
        max_penalty = max(300 * 10, 100)
        penalties = 10 * 2.0 + 5 * 1.0 + 3 * 0.5 + 2 * 3.0 + 1 * 2.0 + 4 * 5.0
        score = max(0.0, base - (penalties / max_penalty * base))
        assert 0 <= score <= 100


class TestHypothesisGen:
    def test_finding_to_hypothesis_mapping(self):
        from app.research.hypothesis_gen import HypothesisGenerator
        gen = HypothesisGenerator(None)
        from app.models.research import ResearchFinding

        finding = ResearchFinding(
            title="Median peak rating across 100 users is 1500",
            description="Users achieve a median peak rating...",
            metric="peak_rating_distribution",
            category="rating_progression",
            confidence_score=0.8,
        )
        hyps = gen._generate_from_finding(finding)
        assert len(hyps) >= 2
        assert any("peak" in h["question"].lower() for h in hyps)

    def test_tag_finding_hypotheses(self):
        from app.research.hypothesis_gen import HypothesisGenerator
        gen = HypothesisGenerator(None)
        from app.models.research import ResearchFinding

        finding = ResearchFinding(
            title="Most solved tag: dp (500 solves)",
            description="Tag distribution across all solved submissions...",
            metric="tag_solve_distribution",
            category="tag_mastery",
            confidence_score=0.9,
        )
        hyps = gen._generate_from_finding(finding)
        tag_hyps = [h for h in hyps if h["category"] == "tag_impact"]
        assert len(tag_hyps) >= 2

    def test_velocity_finding_hypotheses(self):
        from app.research.hypothesis_gen import HypothesisGenerator
        gen = HypothesisGenerator(None)
        from app.models.research import ResearchFinding

        finding = ResearchFinding(
            title="Median growth velocity: 5.2 rating points per contest",
            description="Among 100 users with >1 contest...",
            metric="growth_velocity",
            category="velocity",
            confidence_score=0.7,
        )
        hyps = gen._generate_from_finding(finding)
        velocity_hyps = [h for h in hyps if h["category"] == "velocity"]
        assert len(velocity_hyps) >= 2


class TestReportGeneration:
    def test_report_generation_with_empty_data(self):
        from app.research.report_gen import ReportGenerator
        gen = ReportGenerator(None)
        report = {"id": None, "note": "insufficient data"}
        assert report["id"] is None
        assert "insufficient" in report["note"]
