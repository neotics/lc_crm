from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Iterable

from django.db.models import Avg, Count, F, Max, Q
from django.utils import timezone

from .ml import load_model_artifact, predict_score
from .models import (
    Attendance,
    Enrollment,
    ScoringConfig,
    Student,
    StudentScore,
    Teacher,
    TeacherScore,
)


@dataclass
class Window:
    start_date: date
    start_dt: datetime


class ScoringService:
    @classmethod
    def get_config(cls) -> ScoringConfig:
        config = ScoringConfig.objects.order_by("id").first()
        if config:
            return config
        return ScoringConfig.objects.create()

    @classmethod
    def get_window(cls) -> Window:
        config = cls.get_config()
        now = timezone.now()
        start_dt = now - timedelta(days=config.active_window_days)
        return Window(start_date=start_dt.date(), start_dt=start_dt)

    @classmethod
    def clamp(cls, value: float, low: float = 0.0, high: float = 100.0) -> float:
        return max(low, min(high, round(value, 2)))

    @classmethod
    def apply_inactivity_penalty(cls, score: float, last_activity_at):
        if not last_activity_at:
            return 0.0

        config = cls.get_config()
        elapsed_days = (timezone.now() - last_activity_at).days
        if elapsed_days <= 0:
            return score

        ratio = min(elapsed_days / config.inactivity_penalty_days, 1)
        penalty = config.inactivity_penalty_max * ratio
        return cls.clamp(score - penalty)

    @classmethod
    def determine_risk_level(cls, total_score: float) -> str:
        if total_score >= 75:
            return StudentScore.RiskLevel.LOW
        if total_score >= 50:
            return StudentScore.RiskLevel.MEDIUM
        return StudentScore.RiskLevel.HIGH

    @classmethod
    def student_last_activity_at(cls, student: Student):
        attendance_last = student.attendance_records.aggregate(value=Max("created_at"))["value"]
        grade_last = student.grades.aggregate(value=Max("created_at"))["value"]
        payment_last = student.payments.aggregate(value=Max("created_at"))["value"]
        values = [value for value in [attendance_last, grade_last, payment_last] if value]
        return max(values) if values else None

    @classmethod
    def calculate_attendance_score(cls, student: Student) -> float:
        window = cls.get_window()
        attendances = student.attendance_records.filter(lesson__date__gte=window.start_date)
        total = attendances.count()
        if total == 0:
            return 0.0

        effective_present = attendances.filter(
            status__in=[Attendance.Status.PRESENT, Attendance.Status.LATE, Attendance.Status.EXCUSED]
        ).count()
        ratio = effective_present / total
        if ratio < 0.5:
            return 30.0
        return cls.clamp(ratio * 100)

    @classmethod
    def calculate_grade_score(cls, student: Student) -> float:
        window = cls.get_window()
        average = student.grades.filter(lesson__date__gte=window.start_date).aggregate(value=Avg("grade"))["value"]
        if average is None:
            return 0.0
        return cls.clamp(float(average))

    @classmethod
    def calculate_payment_score(cls, student: Student) -> float:
        debt_count = student.payments.filter(amount_paid__lt=F("amount_due")).count()
        if debt_count == 0:
            return 100.0
        if debt_count == 1:
            return 60.0
        return 20.0

    @classmethod
    def calculate_activity_score(cls, student: Student) -> float:
        window = cls.get_window()
        attendance_points = student.attendance_records.filter(
            lesson__date__gte=window.start_date,
            status__in=[Attendance.Status.PRESENT, Attendance.Status.LATE],
        ).count() * 10
        grade_points = student.grades.filter(lesson__date__gte=window.start_date).count() * 5
        recent_payment_points = student.payments.filter(month__gte=window.start_date).count() * 15
        raw_score = attendance_points + grade_points + recent_payment_points
        return cls.clamp(raw_score)

    @classmethod
    def calculate_attendance_ratio(cls, student: Student) -> float:
        window = cls.get_window()
        attendances = student.attendance_records.filter(lesson__date__gte=window.start_date)
        total = attendances.count()
        if total == 0:
            return 0.0
        effective_present = attendances.filter(
            status__in=[Attendance.Status.PRESENT, Attendance.Status.LATE, Attendance.Status.EXCUSED]
        ).count()
        return round((effective_present / total) * 100, 2)

    @classmethod
    def calculate_average_grade_raw(cls, student: Student) -> float:
        window = cls.get_window()
        average = student.grades.filter(lesson__date__gte=window.start_date).aggregate(value=Avg("grade"))["value"]
        return round(float(average or 0.0), 2)

    @classmethod
    def calculate_debt_months(cls, student: Student) -> int:
        return student.payments.filter(amount_paid__lt=F("amount_due")).count()

    @classmethod
    def calculate_active_enrollments(cls, student: Student) -> int:
        return student.enrollments.filter(status=Enrollment.Status.ACTIVE).count()

    @classmethod
    def calculate_days_since_activity(cls, student: Student) -> int:
        last_activity = cls.student_last_activity_at(student)
        if not last_activity:
            return 999
        return max(0, (timezone.now() - last_activity).days)

    @classmethod
    def build_student_feature_payload(cls, student: Student) -> dict:
        attendance_score = cls.calculate_attendance_score(student)
        grade_score = cls.calculate_grade_score(student)
        payment_score = cls.calculate_payment_score(student)
        activity_score = cls.calculate_activity_score(student)
        return {
            "attendance_score": attendance_score,
            "grade_score": grade_score,
            "payment_score": payment_score,
            "activity_score": activity_score,
            "attendance_ratio": cls.calculate_attendance_ratio(student),
            "average_grade_raw": cls.calculate_average_grade_raw(student),
            "debt_months": cls.calculate_debt_months(student),
            "active_enrollments": cls.calculate_active_enrollments(student),
            "days_since_activity": cls.calculate_days_since_activity(student),
            "last_activity_at": cls.student_last_activity_at(student),
        }

    @classmethod
    def calculate_rule_based_total(cls, feature_payload: dict) -> float:
        config = cls.get_config()
        total_score = (
            feature_payload["attendance_score"] * config.attendance_weight
            + feature_payload["grade_score"] * config.grade_weight
            + feature_payload["payment_score"] * config.payment_weight
            + feature_payload["activity_score"] * config.activity_weight
        )
        return cls.clamp(total_score)

    @classmethod
    def recalculate_student_score(cls, student: Student) -> StudentScore:
        config = cls.get_config()
        feature_payload = cls.build_student_feature_payload(student)
        attendance_score = feature_payload["attendance_score"]
        grade_score = feature_payload["grade_score"]
        payment_score = feature_payload["payment_score"]
        activity_score = feature_payload["activity_score"]
        last_activity_at = feature_payload["last_activity_at"]

        rule_based_score = cls.calculate_rule_based_total(feature_payload)
        rule_based_score = cls.apply_inactivity_penalty(rule_based_score, last_activity_at)
        rule_based_score = cls.clamp(rule_based_score)

        total_score = rule_based_score
        ml_predicted_score = 0.0
        ml_confidence = 0.0
        score_source = StudentScore.ScoreSource.RULE_BASED

        artifact = load_model_artifact("student")
        if config.ml_enabled and artifact and artifact.get("train_rows", 0) >= config.ml_min_training_rows:
            ml_predicted_score, ml_confidence = predict_score(artifact, feature_payload)
            total_score = cls.clamp(
                rule_based_score * (1 - config.ml_blend_weight) + ml_predicted_score * config.ml_blend_weight
            )
            score_source = StudentScore.ScoreSource.ML_BLENDED

        risk_level = cls.determine_risk_level(total_score)

        score_obj, _ = StudentScore.objects.update_or_create(
            student=student,
            defaults={
                "attendance_score": attendance_score,
                "grade_score": grade_score,
                "payment_score": payment_score,
                "activity_score": activity_score,
                "rule_based_score": rule_based_score,
                "ml_predicted_score": ml_predicted_score,
                "ml_confidence": ml_confidence,
                "total_score": total_score,
                "score_source": score_source,
                "risk_level": risk_level,
                "last_activity_at": last_activity_at,
            },
        )
        return score_obj

    @classmethod
    def recalculate_students(cls, students: Iterable[Student]) -> None:
        for student in students:
            cls.recalculate_student_score(student)

    @classmethod
    def teacher_students_queryset(cls, teacher: Teacher):
        return Student.objects.filter(enrollments__course__teacher=teacher).distinct()

    @classmethod
    def calculate_teacher_student_avg_score(cls, teacher: Teacher) -> float:
        student_ids = cls.teacher_students_queryset(teacher).values_list("id", flat=True)
        average = StudentScore.objects.filter(student_id__in=student_ids).aggregate(value=Avg("total_score"))["value"]
        return cls.clamp(float(average or 0.0))

    @classmethod
    def calculate_attendance_control_score(cls, teacher: Teacher) -> float:
        window = cls.get_window()
        lessons = teacher.courses.filter(is_active=True).prefetch_related("lessons", "enrollments")

        expected = 0
        recorded = 0
        for course in lessons:
            lesson_count = course.lessons.filter(date__gte=window.start_date).count()
            enrolled_count = course.enrollments.filter(status=Enrollment.Status.ACTIVE).count()
            expected += lesson_count * enrolled_count
            recorded += Attendance.objects.filter(
                lesson__course=course,
                lesson__date__gte=window.start_date,
            ).count()

        if expected == 0:
            return 0.0
        return cls.clamp((recorded / expected) * 100)

    @classmethod
    def calculate_student_retention_score(cls, teacher: Teacher) -> float:
        window = cls.get_window()
        enrollments = Enrollment.objects.filter(course__teacher=teacher, enrolled_on__lte=timezone.localdate())
        baseline = enrollments.filter(enrolled_on__lte=window.start_date)
        total = baseline.count()
        if total == 0:
            return 100.0
        retained = baseline.filter(
            Q(status=Enrollment.Status.ACTIVE)
            | Q(status=Enrollment.Status.COMPLETED)
            | Q(left_on__isnull=True)
            | Q(left_on__gte=window.start_date)
        ).count()
        return cls.clamp((retained / total) * 100)

    @classmethod
    def calculate_teacher_student_count(cls, teacher: Teacher) -> int:
        return cls.teacher_students_queryset(teacher).count()

    @classmethod
    def calculate_teacher_active_course_count(cls, teacher: Teacher) -> int:
        return teacher.courses.filter(is_active=True).count()

    @classmethod
    def calculate_teacher_high_risk_student_ratio(cls, teacher: Teacher) -> float:
        student_ids = list(cls.teacher_students_queryset(teacher).values_list("id", flat=True))
        if not student_ids:
            return 0.0
        high_risk = StudentScore.objects.filter(student_id__in=student_ids, risk_level=StudentScore.RiskLevel.HIGH).count()
        return cls.clamp((high_risk / len(student_ids)) * 100)

    @classmethod
    def build_teacher_feature_payload(cls, teacher: Teacher, feedback_score: float | None = None) -> dict:
        student_avg_score = cls.calculate_teacher_student_avg_score(teacher)
        attendance_control_score = cls.calculate_attendance_control_score(teacher)
        student_retention_score = cls.calculate_student_retention_score(teacher)
        score_obj, _ = TeacherScore.objects.get_or_create(teacher=teacher)
        feedback = feedback_score if feedback_score is not None else score_obj.feedback_score
        return {
            "student_avg_score": student_avg_score,
            "attendance_control_score": attendance_control_score,
            "student_retention_score": student_retention_score,
            "feedback_score": feedback,
            "student_count": cls.calculate_teacher_student_count(teacher),
            "active_course_count": cls.calculate_teacher_active_course_count(teacher),
            "high_risk_student_ratio": cls.calculate_teacher_high_risk_student_ratio(teacher),
        }

    @classmethod
    def calculate_teacher_rule_based_total(cls, feature_payload: dict) -> float:
        config = cls.get_config()
        total_score = (
            feature_payload["student_avg_score"] * config.teacher_student_avg_weight
            + feature_payload["attendance_control_score"] * config.teacher_attendance_control_weight
            + feature_payload["student_retention_score"] * config.teacher_retention_weight
            + feature_payload["feedback_score"] * config.teacher_feedback_weight
        )
        return cls.clamp(total_score)

    @classmethod
    def recalculate_teacher_score(cls, teacher: Teacher, refresh_students: bool = True) -> TeacherScore:
        config = cls.get_config()
        students = list(cls.teacher_students_queryset(teacher))
        if refresh_students:
            cls.recalculate_students(students)

        score_obj, _ = TeacherScore.objects.get_or_create(teacher=teacher)
        feature_payload = cls.build_teacher_feature_payload(teacher, feedback_score=score_obj.feedback_score)
        rule_based_score = cls.calculate_teacher_rule_based_total(feature_payload)
        total_score = rule_based_score
        ml_predicted_score = 0.0
        ml_confidence = 0.0
        score_source = TeacherScore.ScoreSource.RULE_BASED

        artifact = load_model_artifact("teacher")
        if config.ml_enabled and artifact and artifact.get("train_rows", 0) >= config.teacher_ml_min_training_rows:
            ml_predicted_score, ml_confidence = predict_score(artifact, feature_payload)
            total_score = cls.clamp(
                rule_based_score * (1 - config.ml_blend_weight) + ml_predicted_score * config.ml_blend_weight
            )
            score_source = TeacherScore.ScoreSource.ML_BLENDED

        score_obj.student_avg_score = feature_payload["student_avg_score"]
        score_obj.attendance_control_score = feature_payload["attendance_control_score"]
        score_obj.student_retention_score = feature_payload["student_retention_score"]
        score_obj.rule_based_score = rule_based_score
        score_obj.ml_predicted_score = ml_predicted_score
        score_obj.ml_confidence = ml_confidence
        score_obj.total_score = cls.clamp(total_score)
        score_obj.score_source = score_source
        score_obj.save(
            update_fields=[
                "student_avg_score",
                "attendance_control_score",
                "student_retention_score",
                "rule_based_score",
                "ml_predicted_score",
                "ml_confidence",
                "total_score",
                "score_source",
                "updated_at",
                "last_updated",
            ]
        )
        return score_obj

    @classmethod
    def recalculate_from_student(cls, student: Student) -> StudentScore:
        student_score = cls.recalculate_student_score(student)
        teacher_ids = Teacher.objects.filter(courses__enrollments__student=student).values_list("id", flat=True).distinct()
        for teacher in Teacher.objects.filter(id__in=teacher_ids):
            cls.recalculate_teacher_score(teacher)
        return student_score

    @classmethod
    def recalculate_from_teacher(cls, teacher: Teacher) -> TeacherScore:
        return cls.recalculate_teacher_score(teacher)
