from __future__ import annotations

import json
import math
from pathlib import Path

from django.conf import settings
from django.utils import timezone


ARTIFACT_DIR = Path(settings.BASE_DIR) / "artifacts"
MODEL_PATHS = {
    "student": ARTIFACT_DIR / "student_score_model.json",
    "teacher": ARTIFACT_DIR / "teacher_score_model.json",
}

STUDENT_FEATURE_KEYS = [
    "attendance_score",
    "grade_score",
    "payment_score",
    "activity_score",
    "attendance_ratio",
    "average_grade_raw",
    "debt_months",
    "active_enrollments",
    "days_since_activity",
]

TEACHER_FEATURE_KEYS = [
    "student_avg_score",
    "attendance_control_score",
    "student_retention_score",
    "feedback_score",
    "student_count",
    "active_course_count",
    "high_risk_student_ratio",
]


def ensure_artifact_dir() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)


def get_model_path(model_name: str) -> Path:
    return MODEL_PATHS[model_name]


def load_model_artifact(model_name: str) -> dict | None:
    path = get_model_path(model_name)
    if not path.exists():
        return None
    return json.loads(path.read_text())


def save_model_artifact(model_name: str, artifact: dict) -> Path:
    ensure_artifact_dir()
    path = get_model_path(model_name)
    path.write_text(json.dumps(artifact, indent=2))
    return path


def fit_linear_regression(
    samples: list[dict],
    targets: list[float],
    feature_keys: list[str],
    ridge_alpha: float = 0.1,
) -> dict:
    if len(samples) != len(targets):
        raise ValueError("Samples and targets length mismatch.")
    if len(samples) < 2:
        raise ValueError("At least two samples are required.")

    means = {}
    stds = {}
    design_rows = []

    for key in feature_keys:
        values = [float(sample.get(key, 0.0)) for sample in samples]
        mean = sum(values) / len(values)
        variance = sum((value - mean) ** 2 for value in values) / len(values)
        std = math.sqrt(variance) or 1.0
        means[key] = mean
        stds[key] = std

    for sample in samples:
        row = [1.0]
        for key in feature_keys:
            raw_value = float(sample.get(key, 0.0))
            row.append((raw_value - means[key]) / stds[key])
        design_rows.append(row)

    feature_count = len(feature_keys) + 1
    xtx = [[0.0 for _ in range(feature_count)] for _ in range(feature_count)]
    xty = [0.0 for _ in range(feature_count)]

    for row, target in zip(design_rows, targets):
        for i in range(feature_count):
            xty[i] += row[i] * target
            for j in range(feature_count):
                xtx[i][j] += row[i] * row[j]

    for i in range(1, feature_count):
        xtx[i][i] += ridge_alpha

    coefficients = _solve_linear_system(xtx, xty)
    predictions = [_predict_from_scaled_row(coefficients, row) for row in design_rows]
    mae = sum(abs(pred - actual) for pred, actual in zip(predictions, targets)) / len(targets)
    rmse = math.sqrt(sum((pred - actual) ** 2 for pred, actual in zip(predictions, targets)) / len(targets))

    return {
        "model_type": "ridge_linear_regression",
        "trained_at": timezone.now().isoformat(),
        "train_rows": len(samples),
        "feature_keys": feature_keys,
        "means": means,
        "stds": stds,
        "coefficients": coefficients,
        "metrics": {
            "mae": round(mae, 4),
            "rmse": round(rmse, 4),
        },
    }


def predict_score(artifact: dict, sample: dict) -> tuple[float, float]:
    row = [1.0]
    for key in artifact["feature_keys"]:
        mean = float(artifact["means"][key])
        std = float(artifact["stds"][key]) or 1.0
        value = float(sample.get(key, 0.0))
        row.append((value - mean) / std)

    predicted = _predict_from_scaled_row(artifact["coefficients"], row)
    predicted = max(0.0, min(100.0, round(predicted, 2)))
    rmse = float(artifact.get("metrics", {}).get("rmse", 25.0))
    train_rows = int(artifact.get("train_rows", 0))
    confidence = max(35.0, min(99.0, round(100.0 - rmse + min(train_rows, 200) / 8, 2)))
    return predicted, confidence


def _predict_from_scaled_row(coefficients: list[float], row: list[float]) -> float:
    return sum(weight * value for weight, value in zip(coefficients, row))


def _solve_linear_system(matrix: list[list[float]], vector: list[float]) -> list[float]:
    size = len(vector)
    augmented = [matrix_row[:] + [vector_value] for matrix_row, vector_value in zip(matrix, vector)]

    for col in range(size):
        pivot_row = max(range(col, size), key=lambda row: abs(augmented[row][col]))
        if abs(augmented[pivot_row][col]) < 1e-12:
            continue
        augmented[col], augmented[pivot_row] = augmented[pivot_row], augmented[col]
        pivot = augmented[col][col]

        for j in range(col, size + 1):
            augmented[col][j] /= pivot

        for row in range(size):
            if row == col:
                continue
            factor = augmented[row][col]
            for j in range(col, size + 1):
                augmented[row][j] -= factor * augmented[col][j]

    return [augmented[row][size] for row in range(size)]
