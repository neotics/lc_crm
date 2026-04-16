from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Teacher(TimeStampedModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="teacher_profile",
        null=True,
        blank=True,
        help_text="Teacher login qilishi uchun bog'langan user account.",
    )
    full_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["full_name"]

    def __str__(self) -> str:
        return self.full_name


class Student(TimeStampedModel):
    full_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20, blank=True)
    joined_at = models.DateField(default=timezone.localdate)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["full_name"]

    def __str__(self) -> str:
        return self.full_name


class Course(TimeStampedModel):
    name = models.CharField(max_length=255)
    teacher = models.ForeignKey(
        Teacher,
        on_delete=models.CASCADE,
        related_name="courses",
    )
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Enrollment(TimeStampedModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        DROPPED = "dropped", "Dropped"
        COMPLETED = "completed", "Completed"

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="enrollments",
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="enrollments",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    enrolled_on = models.DateField(default=timezone.localdate)
    left_on = models.DateField(null=True, blank=True)

    class Meta:
        unique_together = ("student", "course")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.student} - {self.course}"


class Lesson(TimeStampedModel):
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="lessons",
    )
    date = models.DateField(default=timezone.localdate)
    topic = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-date"]

    def __str__(self) -> str:
        return f"{self.course} - {self.date}"


class Attendance(TimeStampedModel):
    class Status(models.TextChoices):
        PRESENT = "present", "Present"
        ABSENT = "absent", "Absent"
        LATE = "late", "Late"
        EXCUSED = "excused", "Excused"

    class Participation(models.TextChoices):
        HIGH = "high", "High"
        MEDIUM = "medium", "Medium"
        LOW = "low", "Low"
        NONE = "none", "None"

    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name="attendance_records",
    )
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="attendance_records",
    )
    status = models.CharField(max_length=20, choices=Status.choices)
    participation = models.CharField(
        max_length=20,
        choices=Participation.choices,
        default=Participation.MEDIUM,
    )

    class Meta:
        unique_together = ("lesson", "student")
        ordering = ["-lesson__date"]

    def __str__(self) -> str:
        return f"{self.student} - {self.lesson} - {self.status} - {self.participation}"


class Grade(TimeStampedModel):
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="grades",
    )
    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name="grades",
    )
    grade = models.FloatField(validators=[MinValueValidator(0), MaxValueValidator(100)])

    class Meta:
        ordering = ["-lesson__date"]

    def __str__(self) -> str:
        return f"{self.student} - {self.grade}"


class Payment(TimeStampedModel):
    class Status(models.TextChoices):
        PAID = "paid", "Paid"
        PARTIAL = "partial", "Partial"
        UNPAID = "unpaid", "Unpaid"

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="payments",
    )
    month = models.DateField(help_text="Use first day of month.")
    amount_due = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.UNPAID)

    class Meta:
        unique_together = ("student", "month")
        ordering = ["-month"]

    def __str__(self) -> str:
        return f"{self.student} - {self.month}"

    @property
    def debt_amount(self) -> Decimal:
        return max(self.amount_due - self.amount_paid, Decimal("0.00"))


class ScoringConfig(TimeStampedModel):
    attendance_weight = models.FloatField(default=0.3)
    grade_weight = models.FloatField(default=0.3)
    payment_weight = models.FloatField(default=0.2)
    activity_weight = models.FloatField(default=0.2)
    teacher_student_avg_weight = models.FloatField(default=0.4)
    teacher_attendance_control_weight = models.FloatField(default=0.2)
    teacher_retention_weight = models.FloatField(default=0.2)
    teacher_feedback_weight = models.FloatField(default=0.2)
    inactivity_penalty_max = models.FloatField(default=30.0)
    inactivity_penalty_days = models.PositiveIntegerField(default=30)
    active_window_days = models.PositiveIntegerField(default=30)
    ml_enabled = models.BooleanField(default=True)
    ml_blend_weight = models.FloatField(default=0.7)
    ml_min_training_rows = models.PositiveIntegerField(default=30)
    teacher_ml_min_training_rows = models.PositiveIntegerField(default=5)

    class Meta:
        verbose_name = "Scoring config"
        verbose_name_plural = "Scoring config"

    def __str__(self) -> str:
        return "Scoring configuration"


class StudentScore(TimeStampedModel):
    class ScoreSource(models.TextChoices):
        RULE_BASED = "rule_based", "Rule based"
        ML_BLENDED = "ml_blended", "ML blended"

    class RiskLevel(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"

    student = models.OneToOneField(
        Student,
        on_delete=models.CASCADE,
        related_name="score",
    )
    attendance_score = models.FloatField(default=0.0)
    grade_score = models.FloatField(default=0.0)
    payment_score = models.FloatField(default=0.0)
    activity_score = models.FloatField(default=0.0)
    rule_based_score = models.FloatField(default=0.0)
    ml_predicted_score = models.FloatField(default=0.0)
    ml_confidence = models.FloatField(default=0.0)
    observed_outcome_score = models.FloatField(default=0.0)
    observed_risk_level = models.CharField(
        max_length=10,
        choices=RiskLevel.choices,
        default=RiskLevel.HIGH,
    )
    total_score = models.FloatField(default=0.0, db_index=True)
    score_source = models.CharField(
        max_length=20,
        choices=ScoreSource.choices,
        default=ScoreSource.RULE_BASED,
    )
    risk_level = models.CharField(
        max_length=10,
        choices=RiskLevel.choices,
        default=RiskLevel.HIGH,
        db_index=True,
    )
    last_activity_at = models.DateTimeField(null=True, blank=True)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-total_score"]

    def __str__(self) -> str:
        return f"{self.student} - {self.total_score}"


class TeacherScore(TimeStampedModel):
    class ScoreSource(models.TextChoices):
        RULE_BASED = "rule_based", "Rule based"
        ML_BLENDED = "ml_blended", "ML blended"

    teacher = models.OneToOneField(
        Teacher,
        on_delete=models.CASCADE,
        related_name="score",
    )
    student_avg_score = models.FloatField(default=0.0)
    attendance_control_score = models.FloatField(default=0.0)
    student_retention_score = models.FloatField(default=0.0)
    feedback_score = models.FloatField(default=0.0)
    rule_based_score = models.FloatField(default=0.0)
    ml_predicted_score = models.FloatField(default=0.0)
    ml_confidence = models.FloatField(default=0.0)
    observed_outcome_score = models.FloatField(default=0.0)
    total_score = models.FloatField(default=0.0, db_index=True)
    score_source = models.CharField(
        max_length=20,
        choices=ScoreSource.choices,
        default=ScoreSource.RULE_BASED,
    )
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-total_score"]

    def __str__(self) -> str:
        return f"{self.teacher} - {self.total_score}"
