from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from django.test import TestCase
from django.utils import timezone

from .ml import STUDENT_FEATURE_KEYS, TEACHER_FEATURE_KEYS, fit_linear_regression, get_model_path, save_model_artifact
from .models import Attendance, Course, Enrollment, Grade, Lesson, Payment, Student, Teacher, TeacherScore
from .services import ScoringService
from .views import DashboardView


class ScoringServiceTests(TestCase):
    def setUp(self):
        self._artifact_backup = {}
        for model_name in ["student", "teacher"]:
            path = Path(get_model_path(model_name))
            self._artifact_backup[model_name] = path.read_text() if path.exists() else None

        self.teacher = Teacher.objects.create(full_name="Ali Valiyev")
        self.student = Student.objects.create(full_name="Hasan")
        self.course = Course.objects.create(
            name="IELTS",
            teacher=self.teacher,
            start_date=timezone.localdate() - timedelta(days=60),
        )
        Enrollment.objects.create(student=self.student, course=self.course)
        self.lesson = Lesson.objects.create(course=self.course, date=timezone.localdate() - timedelta(days=1))

    def test_student_score_is_created(self):
        Attendance.objects.create(lesson=self.lesson, student=self.student, status=Attendance.Status.PRESENT)
        Grade.objects.create(student=self.student, lesson=self.lesson, grade=88)
        Payment.objects.create(
            student=self.student,
            month=timezone.localdate().replace(day=1),
            amount_due=Decimal("500000.00"),
            amount_paid=Decimal("500000.00"),
            status=Payment.Status.PAID,
        )

        score = ScoringService.recalculate_student_score(self.student)

        self.assertGreater(score.total_score, 0)
        self.assertEqual(score.risk_level, "low")

    def test_ml_prediction_can_be_applied(self):
        Attendance.objects.create(lesson=self.lesson, student=self.student, status=Attendance.Status.PRESENT)
        Grade.objects.create(student=self.student, lesson=self.lesson, grade=88)
        Payment.objects.create(
            student=self.student,
            month=timezone.localdate().replace(day=1),
            amount_due=Decimal("500000.00"),
            amount_paid=Decimal("500000.00"),
            status=Payment.Status.PAID,
        )

        feature_payload = ScoringService.build_student_feature_payload(self.student)
        target = ScoringService.calculate_rule_based_total(feature_payload)
        artifact = fit_linear_regression(
            [feature_payload, {**feature_payload, "activity_score": 20.0}],
            [target, 40.0],
            STUDENT_FEATURE_KEYS,
        )
        save_model_artifact("student", artifact)
        config = ScoringService.get_config()
        config.ml_enabled = True
        config.ml_min_training_rows = 2
        config.teacher_ml_min_training_rows = 2
        config.save(update_fields=["ml_enabled", "ml_min_training_rows", "teacher_ml_min_training_rows", "updated_at"])

        score = ScoringService.recalculate_student_score(self.student)

        self.assertEqual(score.score_source, "ml_blended")
        self.assertGreater(score.ml_confidence, 0)
        self.assertGreater(score.ml_predicted_score, 0)

    def test_teacher_ml_prediction_can_be_applied(self):
        score, _ = TeacherScore.objects.get_or_create(teacher=self.teacher, defaults={"feedback_score": 90})
        Attendance.objects.create(lesson=self.lesson, student=self.student, status=Attendance.Status.PRESENT)
        Grade.objects.create(student=self.student, lesson=self.lesson, grade=88)
        Payment.objects.create(
            student=self.student,
            month=timezone.localdate().replace(day=1),
            amount_due=Decimal("500000.00"),
            amount_paid=Decimal("500000.00"),
            status=Payment.Status.PAID,
        )
        ScoringService.recalculate_student_score(self.student)
        feature_payload = ScoringService.build_teacher_feature_payload(self.teacher, feedback_score=90)
        target = ScoringService.calculate_teacher_rule_based_total(feature_payload)
        artifact = fit_linear_regression(
            [feature_payload, {**feature_payload, "student_retention_score": 55.0}],
            [target, 58.0],
            TEACHER_FEATURE_KEYS,
        )
        save_model_artifact("teacher", artifact)
        config = ScoringService.get_config()
        config.ml_enabled = True
        config.teacher_ml_min_training_rows = 2
        config.save(update_fields=["ml_enabled", "teacher_ml_min_training_rows", "updated_at"])

        teacher_score = ScoringService.recalculate_teacher_score(self.teacher)

        self.assertEqual(teacher_score.score_source, "ml_blended")
        self.assertGreater(teacher_score.ml_confidence, 0)
        self.assertGreater(teacher_score.ml_predicted_score, 0)

    def tearDown(self):
        for model_name in ["student", "teacher"]:
            path = Path(get_model_path(model_name))
            original_content = self._artifact_backup.get(model_name)
            if original_content is None:
                if path.exists():
                    path.unlink()
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(original_content)


class DashboardViewTests(TestCase):
    def test_calculate_outstanding_payments_sums_all_debts(self):
        student = Student.objects.create(full_name="Zarina")
        current_month = timezone.localdate().replace(day=1)

        Payment.objects.create(
            student=student,
            month=current_month,
            amount_due=Decimal("500000.00"),
            amount_paid=Decimal("350000.00"),
            status=Payment.Status.PARTIAL,
        )
        Payment.objects.create(
            student=student,
            month=(current_month - timedelta(days=31)).replace(day=1),
            amount_due=Decimal("400000.00"),
            amount_paid=Decimal("0.00"),
            status=Payment.Status.UNPAID,
        )
        Payment.objects.create(
            student=student,
            month=(current_month - timedelta(days=62)).replace(day=1),
            amount_due=Decimal("450000.00"),
            amount_paid=Decimal("450000.00"),
            status=Payment.Status.PAID,
        )

        outstanding_payments = DashboardView.calculate_outstanding_payments()

        self.assertEqual(outstanding_payments, Decimal("550000"))
