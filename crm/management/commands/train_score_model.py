from django.core.management.base import BaseCommand, CommandError

from crm.ml import (
    STUDENT_FEATURE_KEYS,
    TEACHER_FEATURE_KEYS,
    fit_linear_regression,
    save_model_artifact,
)
from crm.models import Student, StudentScore, Teacher, TeacherScore
from crm.services import ScoringService


def train_models() -> dict:
    student_rows = _train_student_model()
    teacher_rows = _train_teacher_model()

    for student in Student.objects.filter(is_active=True):
        ScoringService.recalculate_from_student(student)
    for teacher in Teacher.objects.filter(is_active=True):
        ScoringService.recalculate_from_teacher(teacher)

    return {
        "student": student_rows,
        "teacher": teacher_rows,
    }


def _train_student_model() -> dict:
    students = list(Student.objects.filter(is_active=True))
    if not students:
        raise CommandError("No active students found for student model training.")

    config = ScoringService.get_config()
    if len(students) < config.ml_min_training_rows:
        raise CommandError(
            f"Not enough student rows for training. Required: {config.ml_min_training_rows}, found: {len(students)}."
        )

    samples = []
    targets = []
    for student in students:
        feature_payload = ScoringService.build_student_feature_payload(student)
        score_obj, _ = StudentScore.objects.get_or_create(student=student)
        target = score_obj.observed_outcome_score or ScoringService.calculate_rule_based_total(feature_payload)
        samples.append(feature_payload)
        targets.append(target)

    artifact = fit_linear_regression(samples, targets, STUDENT_FEATURE_KEYS)
    path = save_model_artifact("student", artifact)
    return {"path": path, "artifact": artifact}


def _train_teacher_model() -> dict:
    teachers = list(Teacher.objects.filter(is_active=True))
    if not teachers:
        raise CommandError("No active teachers found for teacher model training.")

    config = ScoringService.get_config()
    if len(teachers) < config.teacher_ml_min_training_rows:
        raise CommandError(
            "Not enough teacher rows for training. "
            f"Required: {config.teacher_ml_min_training_rows}, found: {len(teachers)}."
        )

    samples = []
    targets = []
    for teacher in teachers:
        score_obj, _ = TeacherScore.objects.get_or_create(teacher=teacher)
        feature_payload = ScoringService.build_teacher_feature_payload(teacher, feedback_score=score_obj.feedback_score)
        target = score_obj.observed_outcome_score or ScoringService.calculate_teacher_rule_based_total(feature_payload)
        samples.append(feature_payload)
        targets.append(target)

    artifact = fit_linear_regression(samples, targets, TEACHER_FEATURE_KEYS)
    path = save_model_artifact("teacher", artifact)
    return {"path": path, "artifact": artifact}


class Command(BaseCommand):
    help = "Train lightweight ML models for student and teacher score prediction using CRM data."

    def handle(self, *args, **options):
        results = train_models()
        student_artifact = results["student"]["artifact"]
        teacher_artifact = results["teacher"]["artifact"]
        self.stdout.write(
            self.style.SUCCESS(
                "Student model: "
                f"rows={student_artifact['train_rows']}, "
                f"MAE={student_artifact['metrics']['mae']}, "
                f"RMSE={student_artifact['metrics']['rmse']}, "
                f"path={results['student']['path']}"
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                "Teacher model: "
                f"rows={teacher_artifact['train_rows']}, "
                f"MAE={teacher_artifact['metrics']['mae']}, "
                f"RMSE={teacher_artifact['metrics']['rmse']}, "
                f"path={results['teacher']['path']}"
            )
        )
