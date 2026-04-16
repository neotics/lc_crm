from django.contrib import admin
from django.contrib import messages
from django.template.response import TemplateResponse

from .management.commands.train_score_model import train_models
from .ml import load_model_artifact
from .models import (
    Attendance,
    Course,
    Enrollment,
    Grade,
    Lesson,
    Payment,
    ScoringConfig,
    Student,
    StudentScore,
    Teacher,
    TeacherScore,
)
from .services import ScoringService


def analytics_dashboard_view(request):
    if request.method == "POST" and request.POST.get("action") == "retrain_ml_models":
        results = train_models()
        messages.success(
            request,
            "ML models retrained successfully. "
            f"Student rows={results['student']['artifact']['train_rows']}, "
            f"Teacher rows={results['teacher']['artifact']['train_rows']}.",
        )

    context = dict(
        admin.site.each_context(request),
        title="Analytics dashboard",
        top_students=StudentScore.objects.select_related("student").order_by("-total_score")[:10],
        high_risk_students=StudentScore.objects.select_related("student").filter(
            risk_level=StudentScore.RiskLevel.HIGH
        )[:10],
        teacher_ranking=TeacherScore.objects.select_related("teacher").order_by("-total_score")[:10],
        student_ml_model=load_model_artifact("student"),
        teacher_ml_model=load_model_artifact("teacher"),
    )
    return TemplateResponse(request, "admin/analytics_dashboard.html", context)


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ("full_name", "phone", "is_active")
    search_fields = ("full_name", "phone")


@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ("full_name", "phone", "user", "is_active")
    search_fields = ("full_name", "phone", "user__username", "user__email")


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("name", "teacher", "start_date", "is_active")
    list_filter = ("is_active", "teacher")
    search_fields = ("name",)


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ("student", "course", "status", "enrolled_on", "left_on")
    list_filter = ("status", "course")


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ("course", "date", "topic")
    list_filter = ("course", "date")


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ("student", "lesson", "status", "participation")
    list_filter = ("status", "participation", "lesson__course")


@admin.register(Grade)
class GradeAdmin(admin.ModelAdmin):
    list_display = ("student", "lesson", "grade")
    list_filter = ("lesson__course",)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("student", "month", "amount_due", "amount_paid", "status", "debt_amount")
    list_filter = ("status", "month")


@admin.register(StudentScore)
class StudentScoreAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "total_score",
        "rule_based_score",
        "ml_predicted_score",
        "risk_level",
        "score_source",
        "last_updated",
    )
    list_filter = ("risk_level",)
    search_fields = ("student__full_name",)
    ordering = ("-total_score",)


@admin.register(TeacherScore)
class TeacherScoreAdmin(admin.ModelAdmin):
    list_display = (
        "teacher",
        "total_score",
        "student_avg_score",
        "attendance_control_score",
        "student_retention_score",
        "feedback_score",
        "rule_based_score",
        "ml_predicted_score",
        "score_source",
        "last_updated",
    )
    search_fields = ("teacher__full_name",)
    ordering = ("-total_score",)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        ScoringService.recalculate_from_teacher(obj.teacher)


@admin.register(ScoringConfig)
class ScoringConfigAdmin(admin.ModelAdmin):
    list_display = (
        "attendance_weight",
        "grade_weight",
        "payment_weight",
        "activity_weight",
        "active_window_days",
        "inactivity_penalty_max",
    )
