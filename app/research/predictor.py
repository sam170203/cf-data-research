from __future__ import annotations

import json
import logging
import pickle
from datetime import UTC, datetime
from typing import Any

import numpy as np
import pandas as pd
import shap
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import LogisticRegression, LinearRegression
from sklearn.metrics import (
    accuracy_score, f1_score, roc_auc_score,
    mean_absolute_error, mean_squared_error, r2_score,
    classification_report, confusion_matrix,
)
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier, XGBRegressor

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models.research import PredictionRun
from app.research.features import FeatureComputer, TAG_COLUMNS

logger = logging.getLogger("research.predictor")

BASE_FEATURES = [
    "total_submissions", "total_solved", "total_contests",
    "submissions_per_day", "active_days",
    "max_inactivity_streak", "median_inactivity_gap",
    "avg_contest_delta", "rating_volatility",
    "first_rating", "rating_gain_total",
    "max_win_streak", "max_loss_streak",
    "tag_diversity", "hardest_solved_tag_rating", "avg_solved_rating",
    "growth_velocity", "growth_acceleration",
    "rating_volatility_recent", "contests_last_90d",
    "activity_last_30d", "activity_last_60d", "activity_last_90d",
    "solved_last_30d", "solved_last_60d", "solved_last_90d",
]

TAG_FEATURES = TAG_COLUMNS

ALL_FEATURES = BASE_FEATURES + TAG_FEATURES

CLASSIFICATION_TASKS = {
    "expert_6mo": {
        "target": "target_expert_6mo",
        "description": "Reached Expert (1600+) within 6 months",
    },
    "cm_12mo": {
        "target": "target_cm_12mo",
        "description": "Reached Candidate Master (1900+) within 12 months",
    },
    "master_12mo": {
        "target": "target_master_12mo",
        "description": "Reached Master (2100+) within 12 months",
    },
    "gain_100_90d": {
        "target": "target_gain_100_90d",
        "description": "Gained 100+ rating within any 90-day window",
    },
    "expert_12mo": {
        "target": "target_expert_12mo",
        "description": "Reached Expert (1600+) within 12 months",
    },
    "plateau_risk": {
        "target": "target_plateau_risk",
        "description": "Stagnating — minimal growth in last 3 contests",
    },
}

REGRESSION_TASKS = {
    "rating_3mo": {
        "target": "target_rating_3mo",
        "description": "Rating after 3 months from first contest",
    },
    "rating_6mo": {
        "target": "target_rating_6mo",
        "description": "Rating after 6 months from first contest",
    },
    "rating_12mo": {
        "target": "target_rating_12mo",
        "description": "Rating after 12 months from first contest",
    },
    "rating_90d": {
        "target": "target_rating_90d",
        "description": "Rating after 90 days from first contest",
    },
    "rating_180d": {
        "target": "target_rating_180d",
        "description": "Rating after 180 days from first contest",
    },
}


class Predictor:
    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._sf = session_factory
        self.feature_computer = FeatureComputer(session_factory)
        self.models: dict[str, Any] = {}
        self.results: dict[str, Any] = {}

    async def run_full_pipeline(self) -> dict[str, Any]:
        logger.info("=== Predictive Pipeline Start ===")

        df = await self.feature_computer.build_feature_matrix(include_labels=True)
        logger.info("Feature matrix: %d rows, %d cols, labels: expert=%d cm=%d master=%d",
                     len(df), len(df.columns),
                     (df["target_expert_6mo"] >= 0).sum(),
                     (df["target_cm_12mo"] >= 0).sum(),
                     (df["target_master_12mo"] >= 0).sum())

        logger.info("=== Classification Tasks ===")
        class_results = {}
        for task_name, task_config in CLASSIFICATION_TASKS.items():
            logger.info("Training: %s", task_config["description"])
            result = self._train_classification_pipeline(
                df, task_config["target"], task_name
            )
            class_results[task_name] = result

        logger.info("=== Regression Tasks ===")
        reg_results = {}
        for task_name, task_config in REGRESSION_TASKS.items():
            logger.info("Training: %s", task_config["description"])
            result = self._train_regression_pipeline(
                df, task_name, task_config["description"], task_config,
            )
            reg_results[task_name] = result

        results = {
            "classification": class_results,
            "regression": reg_results,
            "feature_shape": list(df.shape),
            "timestamp": datetime.now(UTC).isoformat(),
        }
        self.results = results

        # Store results to DB
        async with self._sf() as session:
            for task_name, task_result in class_results.items():
                if "error" in task_result:
                    continue
                best = task_result.get("best_model")
                best_metrics = task_result.get(best, {})
                session.add(PredictionRun(
                    task_type="classification",
                    task_name=task_name,
                    model_type=best or "unknown",
                    accuracy=best_metrics.get("accuracy"),
                    f1_score=best_metrics.get("f1"),
                    roc_auc=best_metrics.get("roc_auc"),
                    mae=None, rmse=None, r2=None,
                    feature_importance=task_result.get("feature_importance"),
                    sample_size=task_result.get("target_distribution", {}).get("positive", 0)
                    + task_result.get("target_distribution", {}).get("negative", 0),
                ))
            for task_name, task_result in reg_results.items():
                if "error" in task_result:
                    continue
                best = task_result.get("best_model")
                best_metrics = task_result.get(best, {})
                session.add(PredictionRun(
                    task_type="regression",
                    task_name=task_name,
                    model_type=best or "unknown",
                    mae=best_metrics.get("mae"),
                    rmse=best_metrics.get("rmse"),
                    r2=best_metrics.get("r2"),
                    accuracy=None, f1_score=None, roc_auc=None,
                    feature_importance=task_result.get("feature_importance"),
                    sample_size=best_metrics.get("test_size", 0),
                ))
            await session.commit()
            logger.info("Stored %d prediction runs to DB",
                        len(class_results) + len(reg_results))

        logger.info("=== Predictive Pipeline Complete ===")
        return results

    def _train_classification_pipeline(
        self, df: pd.DataFrame, target_col: str, task_name: str
    ) -> dict[str, Any]:
        valid = df[df[target_col].notna() & (df[target_col] >= 0)].copy()
        if len(valid) < 20:
            return {"error": f"Insufficient labeled data: {len(valid)}"}

        X = valid[ALL_FEATURES].fillna(0)
        y = valid[target_col].astype(int)

        # Handle class imbalance
        pos_ratio = y.mean()
        logger.info(
            "  Task %s: %d samples, pos_ratio=%.2f",
            task_name, len(valid), pos_ratio,
        )

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.25, random_state=42, stratify=y,
        )

        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)

        models = {
            "logistic_regression": LogisticRegression(
                max_iter=1000, class_weight="balanced", random_state=42,
            ),
            "random_forest": RandomForestClassifier(
                n_estimators=200, max_depth=10,
                class_weight="balanced", random_state=42,
                n_jobs=-1,
            ),
            "xgboost": XGBClassifier(
                n_estimators=200, max_depth=6, learning_rate=0.1,
                scale_pos_weight=(1 - pos_ratio) / max(pos_ratio, 0.01),
                random_state=42, eval_metric="logloss",
            ),
        }

        results = {}
        best_model = None
        best_f1 = -1

        for name, model in models.items():
            try:
                if name == "xgboost":
                    model.fit(X_train, y_train)
                    y_pred = model.predict(X_test)
                    y_prob = model.predict_proba(X_test)[:, 1]
                    importances = model.feature_importances_
                else:
                    model.fit(X_train_scaled, y_train)
                    y_pred = model.predict(X_test_scaled)
                    y_prob = model.predict_proba(X_test_scaled)[:, 1]
                    importances = (
                        model.coef_[0] if hasattr(model, "coef_")
                        else model.feature_importances_
                    )

                acc = accuracy_score(y_test, y_pred)
                f1 = f1_score(y_test, y_pred, zero_division=0)
                roc = roc_auc_score(y_test, y_prob) if len(set(y_test)) > 1 else 0.0
                cm = confusion_matrix(y_test, y_pred).tolist()

                results[name] = {
                    "accuracy": round(acc, 4),
                    "f1": round(f1, 4),
                    "roc_auc": round(roc, 4),
                    "confusion_matrix": cm,
                    "test_size": int(len(y_test)),
                }

                if f1 > best_f1:
                    best_f1 = f1
                    best_model = name

                logger.info(
                    "  %s: acc=%.3f f1=%.3f roc=%.3f",
                    name, acc, f1, roc,
                )
            except Exception as e:
                logger.warning("  %s failed: %s", name, e)
                results[name] = {"error": str(e)}

        if best_model:
            results["best_model"] = best_model
            results["feature_importance"] = self._compute_feature_importance(
                X.columns.tolist(), importances if best_model else [], 20
            )
            results["shap_values"] = self._compute_shap_summary(
                models[best_model], X_test, X.columns.tolist(), 15,
            )

        results["target_distribution"] = {
            "positive": int(y.sum()),
            "negative": int((1 - y).sum()),
            "ratio": round(pos_ratio, 3),
        }

        return results

    def _train_regression_pipeline(
        self, df: pd.DataFrame, task_name: str, description: str,
        task_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        target_col = (task_config or {}).get("target", "current_rating")
        valid = df[df[target_col] >= 0].copy()
        if len(valid) < 20:
            return {"error": f"Insufficient data ({target_col}): {len(valid)}"}

        X = valid[ALL_FEATURES].fillna(0)
        y = valid[target_col].values

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.25, random_state=42,
        )

        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)

        models = {
            "linear_regression": LinearRegression(),
            "random_forest": RandomForestRegressor(
                n_estimators=200, max_depth=10, random_state=42, n_jobs=-1,
            ),
            "xgboost": XGBRegressor(
                n_estimators=200, max_depth=6, learning_rate=0.1,
                random_state=42,
            ),
        }

        results = {}
        best_model = None
        best_r2 = -999

        for name, model in models.items():
            try:
                if name == "xgboost":
                    model.fit(X_train, y_train)
                    y_pred = model.predict(X_test)
                else:
                    model.fit(X_train_scaled, y_train)
                    y_pred = model.predict(X_test_scaled)

                mae = mean_absolute_error(y_test, y_pred)
                rmse = np.sqrt(mean_squared_error(y_test, y_pred))
                r2 = r2_score(y_test, y_pred)

                results[name] = {
                    "mae": round(mae, 2),
                    "rmse": round(rmse, 2),
                    "r2": round(r2, 4),
                    "test_size": int(len(y_test)),
                }

                if r2 > best_r2:
                    best_r2 = r2
                    best_model = name

                logger.info(
                    "  %s: mae=%.1f rmse=%.1f r2=%.3f",
                    name, mae, rmse, r2,
                )
            except Exception as e:
                logger.warning("  %s failed: %s", name, e)
                results[name] = {"error": str(e)}

        if best_model:
            results["best_model"] = best_model
            results["feature_importance"] = self._compute_feature_importance(
                X.columns.tolist(), (
                    models[best_model].coef_ if hasattr(models[best_model], "coef_")
                    else models[best_model].feature_importances_
                ), 20,
            )

        return results

    def _compute_feature_importance(
        self, feature_names: list[str], importances: np.ndarray, top_n: int = 20
    ) -> list[dict[str, Any]]:
        indices = np.argsort(np.abs(importances))[::-1][:top_n]
        return [
            {"feature": feature_names[i], "importance": round(float(importances[i]), 4)}
            for i in indices
        ]

    def _compute_shap_summary(
        self, model: Any, X: pd.DataFrame, feature_names: list[str], top_n: int = 15
    ) -> list[dict[str, Any]]:
        try:
            X_in = X.reset_index(drop=True) if isinstance(X, pd.DataFrame) else X
            X_np = np.asarray(X_in, dtype=np.float64)

            try:
                explainer = shap.TreeExplainer(model, feature_perturbation="tree_path_dependent")
                shap_vals = explainer.shap_values(X_np)
            except Exception:
                explainer = shap.Explainer(model, X_np)
                shap_vals = explainer(X_np).values

            if isinstance(shap_vals, list):
                shap_vals = shap_vals[1] if len(shap_vals) > 1 else shap_vals[0]
            elif shap_vals.ndim == 3:
                shap_vals = shap_vals[..., 1]

            if shap_vals.ndim != 2 or shap_vals.shape[1] != len(feature_names):
                raise ValueError(f"Unexpected SHAP shape: {shap_vals.shape}")

            mean_shap = np.abs(shap_vals).mean(axis=0)
            indices = np.argsort(mean_shap)[::-1][:top_n]

            return [
                {"feature": feature_names[i], "mean_abs_shap": round(float(mean_shap[i]), 4)}
                for i in indices
            ]
        except Exception as e:
            logger.warning("SHAP computation failed: %s", e)
            return [{"error": str(e)}]

    def get_model_summary(self, results: dict[str, Any] | None = None) -> str:
        r = results or self.results
        if not r:
            return "No results available"

        lines = []
        lines.append("=== Predictive Model Summary ===")
        lines.append(f"Feature matrix: {r.get('feature_shape', ['?', '?'])}")

        for task_type in ["classification", "regression"]:
            tasks = r.get(task_type, {})
            if not tasks:
                continue
            lines.append(f"\n--- {task_type.title()} ---")
            for task_name, task_result in tasks.items():
                if "error" in task_result:
                    lines.append(f"  {task_name}: ERROR - {task_result['error']}")
                    continue
                best = task_result.get("best_model", "?")
                metrics = task_result.get(best, {})
                if task_type == "classification":
                    lines.append(
                        f"  {task_name}: best={best} "
                        f"acc={metrics.get('accuracy','?')} "
                        f"f1={metrics.get('f1','?')} "
                        f"roc={metrics.get('roc_auc','?')}"
                    )
                else:
                    lines.append(
                        f"  {task_name}: best={best} "
                        f"mae={metrics.get('mae','?')} "
                        f"rmse={metrics.get('rmse','?')} "
                        f"r2={metrics.get('r2','?')}"
                    )

        return "\n".join(lines)
