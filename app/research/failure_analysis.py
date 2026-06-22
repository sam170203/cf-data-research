from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.research.features import FeatureComputer
from app.research.predictor import ALL_FEATURES, CLASSIFICATION_TASKS

logger = logging.getLogger("research.failure_analysis")


class FailureAnalyzer:
    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._sf = session_factory

    async def analyze(
        self, df: pd.DataFrame, task_name: str, model: Any,
        target_col: str, feature_cols: list[str] | None = None,
        X: pd.DataFrame | None = None, y_true: pd.Series | None = None,
    ) -> dict[str, Any]:
        cols = feature_cols or ALL_FEATURES

        if X is None or y_true is None:
            valid = df[df[target_col] >= 0].copy()
            if len(valid) < 10:
                return {"error": f"Insufficient data: {len(valid)}"}
            X = valid[cols].fillna(0)
            y_true = valid[target_col].astype(int)
        else:
            valid = df

        try:
            y_prob = model.predict_proba(X)[:, 1]
        except Exception:
            y_prob = model.predict(X)

        y_pred = (y_prob > 0.5).astype(int)

        is_fp = (y_pred == 1) & (y_true == 0)
        is_fn = (y_pred == 0) & (y_true == 1)

        fp_mask = is_fp.values if hasattr(is_fp, 'values') else is_fp
        fn_mask = is_fn.values if hasattr(is_fn, 'values') else is_fn
        false_positives = valid.loc[is_fp[is_fp].index].head(10) if is_fp.sum() > 0 else valid.iloc[:0]
        false_negatives = valid.loc[is_fn[is_fn].index].head(10) if is_fn.sum() > 0 else valid.iloc[:0]

        fp_handles = false_positives["handle"].tolist() if "handle" in false_positives.columns else []
        fn_handles = false_negatives["handle"].tolist() if "handle" in false_negatives.columns else []

        fp_profiles = []
        for _, row in false_positives.iterrows():
            profile = self._profile_misclassified(row, predicted=1, actual=0)
            fp_profiles.append(profile)

        fn_profiles = []
        for _, row in false_negatives.iterrows():
            profile = self._profile_misclassified(row, predicted=0, actual=1)
            fn_profiles.append(profile)

        hypotheses = self._generate_hypotheses(
            task_name, fp_profiles, fn_profiles,
        )

        return {
            "task": task_name,
            "false_positive_count": int(((y_pred == 1) & (y_true == 0)).sum()),
            "false_negative_count": int(((y_pred == 0) & (y_true == 1)).sum()),
            "false_positive_handles": fp_handles,
            "false_negative_handles": fn_handles,
            "false_positive_profiles": fp_profiles[:5],
            "false_negative_profiles": fn_profiles[:5],
            "hypotheses": hypotheses,
        }

    def _profile_misclassified(
        self, row: pd.Series, predicted: int, actual: int
    ) -> dict[str, Any]:
        return {
            "handle": row.get("handle", "?"),
            "rating": int(row.get("current_rating", 0)),
            "total_contests": int(row.get("total_contests", 0)),
            "total_solved": int(row.get("total_solved", 0)),
            "submissions_per_day": float(row.get("submissions_per_day", 0)),
            "growth_velocity": float(row.get("growth_velocity", 0)),
            "growth_acceleration": float(row.get("growth_acceleration", 0)),
            "rating_volatility": float(row.get("rating_volatility", 0)),
            "tag_diversity": int(row.get("tag_diversity", 0)),
            "max_inactivity_streak": int(row.get("max_inactivity_streak", 0)),
            "median_inactivity_gap": float(row.get("median_inactivity_gap", 0)),
            "activity_last_90d": int(row.get("activity_last_90d", 0)),
            "solved_last_90d": int(row.get("solved_last_90d", 0)),
            "contests_last_90d": int(row.get("contests_last_90d", 0)),
            "avg_solved_rating": float(row.get("avg_solved_rating", 0)),
        }

    def _generate_hypotheses(
        self, task_name: str,
        fp_profiles: list[dict[str, Any]],
        fn_profiles: list[dict[str, Any]],
    ) -> list[str]:
        hypotheses = []

        _NUMERIC = {
            "rating", "total_contests", "total_solved", "submissions_per_day",
            "growth_velocity", "growth_acceleration", "rating_volatility",
            "tag_diversity", "max_inactivity_streak", "median_inactivity_gap",
            "activity_last_90d", "solved_last_90d", "contests_last_90d",
            "avg_solved_rating",
        }
        avg_fp = {k: np.mean([p[k] for p in fp_profiles])
                  for k in _NUMERIC if fp_profiles} if fp_profiles else {}
        avg_fn = {k: np.mean([p[k] for p in fn_profiles])
                  for k in _NUMERIC if fn_profiles} if fn_profiles else {}

        if fp_profiles:
            if avg_fp.get("total_solved", 0) > avg_fn.get("total_solved", 0) * 1.5:
                hypotheses.append(
                    f"High solve volume alone may not predict {task_name} - "
                    f"false positives solve {avg_fp['total_solved']:.0f} problems on average "
                    f"but fail to reach the target"
                )

            if avg_fp.get("total_contests", 0) < 10:
                hypotheses.append(
                    f"Insufficient contest participation may cause overprediction for {task_name} - "
                    f"false positives average only {avg_fp['total_contests']:.0f} contests"
                )
            if avg_fp.get("growth_velocity", 0) < 0:
                hypotheses.append(
                    f"Negative growth velocity despite high activity is a risk signal for {task_name} - "
                    f"false positives have avg velocity {avg_fp['growth_velocity']:.1f}"
                )

            if avg_fp.get("growth_acceleration", 0) < -5:
                hypotheses.append(
                    f"Decelerating growth (acceleration={avg_fp['growth_acceleration']:.1f}) signals "
                    f"false positives are losing momentum for {task_name}"
                )

            if fn_profiles and avg_fp.get("tag_diversity", 0) < avg_fn.get("tag_diversity", 0) * 0.7:
                hypotheses.append(
                    f"Narrow tag diversity characterises false positives for {task_name} - "
                    f"they cover {avg_fp['tag_diversity']:.0f} tags vs {avg_fn['tag_diversity']:.0f} for "
                    f"false negatives, suggesting breadth matters for reaching target"
                )

            if fn_profiles and avg_fp.get("avg_solved_rating", 0) < avg_fn.get("avg_solved_rating", 0) * 0.85:
                hypotheses.append(
                    f"False positives solve easier problems (avg rating {avg_fp['avg_solved_rating']:.0f} vs "
                    f"{avg_fn['avg_solved_rating']:.0f}) for {task_name} - problem difficulty matters more than volume"
                )

            if fn_profiles and avg_fp.get("contests_last_90d", 0) < avg_fn.get("contests_last_90d", 0) * 0.5:
                hypotheses.append(
                    f"Recent contest participation strongly separates FP from FN for {task_name} - "
                    f"false positives average {avg_fp['contests_last_90d']:.1f} contests in 90d vs "
                    f"{avg_fn['contests_last_90d']:.1f} for false negatives"
                )

            if avg_fp.get("rating_volatility", 0) > 80:
                hypotheses.append(
                    f"High rating volatility (σ={avg_fp['rating_volatility']:.0f}) is a risk marker for "
                    f"{task_name} overprediction - inconsistent performers are less likely to sustain growth"
                )

            if avg_fp.get("solved_last_90d", 0) < 5 and avg_fp.get("total_solved", 0) > 50:
                hypotheses.append(
                    f"Low recent solve volume ({avg_fp['solved_last_90d']:.0f} in 90d) despite high lifetime "
                    f"solves ({avg_fp['total_solved']:.0f}) signals stagnation for {task_name}"
                )

        if fn_profiles:
            if avg_fn.get("growth_velocity", 0) > 10:
                hypotheses.append(
                    f"High recent growth velocity ({avg_fn['growth_velocity']:.1f}) is underweighted in "
                    f"{task_name} prediction - false negatives show strong recent momentum"
                )

            if avg_fn.get("activity_last_90d", 0) > 100:
                hypotheses.append(
                    f"High recent activity ({avg_fn['activity_last_90d']:.0f} submissions in 90d) is "
                    f"under-predicted for {task_name} - false negatives show strong practice habits"
                )
            if avg_fn.get("max_inactivity_streak", 0) < 30:
                hypotheses.append(
                    f"Low inactivity streaks ({avg_fn['max_inactivity_streak']:.0f} days max) correlate with "
                    f"underprediction for {task_name} - consistent users are more likely to grow"
                )

            if avg_fn.get("growth_acceleration", 0) > 10:
                hypotheses.append(
                    f"Accelerating growth (acceleration={avg_fn['growth_acceleration']:.1f}) is missed by "
                    f"the model for {task_name} - false negatives show increasing momentum"
                )

            if fp_profiles and avg_fn.get("avg_solved_rating", 0) > avg_fp.get("avg_solved_rating", 0) * 1.15:
                hypotheses.append(
                    f"False negatives tackle harder problems (avg solved rating {avg_fn['avg_solved_rating']:.0f} vs "
                    f"{avg_fp['avg_solved_rating']:.0f}) for {task_name} - challenge level predicts growth"
                )

            if avg_fn.get("solved_last_90d", 0) > 20:
                hypotheses.append(
                    f"High recent solve volume ({avg_fn['solved_last_90d']:.0f} solved in 90d) is "
                    f"underweighted for {task_name} - false negatives show intense current practice"
                )

            if avg_fn.get("submissions_per_day", 0) > 5:
                hypotheses.append(
                    f"High daily practice frequency ({avg_fn['submissions_per_day']:.2f} subs/day) correlates "
                    f"with underprediction for {task_name}"
                )

            if avg_fn.get("median_inactivity_gap", 0) < 2:
                hypotheses.append(
                    f"Very short inactivity gaps (median {avg_fn['median_inactivity_gap']:.1f} days) "
                    f"characterize false negatives for {task_name} - near-daily practice drives growth"
                )

        if fp_profiles and fn_profiles:
            fp_rating = avg_fp.get("rating", 0)
            fn_rating = avg_fn.get("rating", 0)
            if fp_rating and fn_rating and abs(fp_rating - fn_rating) > 100:
                hypotheses.append(
                    f"Current rating gap between FP (avg={fp_rating:.0f}) and FN (avg={fn_rating:.0f}) "
                    f"suggests the model is overconfident at certain rating ranges for {task_name}"
                )

        return hypotheses
