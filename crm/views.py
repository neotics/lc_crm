from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Avg, Count, F, Q, Sum
from django.shortcuts import get_object_or_404
from django.views.generic import DetailView, ListView, TemplateView
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from .ml import load_model_artifact
from .models import Course, Enrollment, Payment, Student, StudentScore, Teacher, TeacherScore
from .serializers import StudentScoreSerializer, TeacherScoreSerializer
from .services import ScoringService


class StudentScoreDetailView(APIView):
    def get(self, request, pk: int):
        student = get_object_or_404(Student, pk=pk)
        score = ScoringService.recalculate_student_score(student)
        return Response(StudentScoreSerializer(score).data)


class TeacherScoreDetailView(APIView):
    def get(self, request, pk: int):
        teacher = get_object_or_404(Teacher, pk=pk)
        score = ScoringService.recalculate_teacher_score(teacher)
        return Response(TeacherScoreSerializer(score).data)


class TopStudentsView(generics.ListAPIView):
    serializer_class = StudentScoreSerializer

    def get_queryset(self):
        student_ids = Student.objects.filter(is_active=True).values_list("id", flat=True)
        for student in Student.objects.filter(id__in=student_ids):
            ScoringService.recalculate_student_score(student)
        return StudentScore.objects.select_related("student").order_by("-total_score")[:10]


class RiskyStudentsView(generics.ListAPIView):
    serializer_class = StudentScoreSerializer

    def get_queryset(self):
        students = Student.objects.filter(is_active=True)
        for student in students:
            ScoringService.recalculate_student_score(student)
        return StudentScore.objects.select_related("student").filter(risk_level=StudentScore.RiskLevel.HIGH).order_by(
            "total_score"
        )


class TeacherRankingView(generics.ListAPIView):
    serializer_class = TeacherScoreSerializer

    def get_queryset(self):
        for teacher in Teacher.objects.filter(is_active=True):
            ScoringService.recalculate_teacher_score(teacher)
        return TeacherScore.objects.select_related("teacher").order_by("-total_score")


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "crm/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        active_students = Student.objects.filter(is_active=True)
        active_teachers = Teacher.objects.filter(is_active=True)
        active_courses = Course.objects.filter(is_active=True)

        for student in active_students:
            ScoringService.recalculate_student_score(student)
        for teacher in active_teachers:
            ScoringService.recalculate_teacher_score(teacher)

        top_students = StudentScore.objects.select_related("student").order_by("-total_score")[:10]
        risky_students = StudentScore.objects.select_related("student").filter(
            risk_level=StudentScore.RiskLevel.HIGH
        )[:10]
        teacher_ranking = TeacherScore.objects.select_related("teacher").order_by("-total_score")[:10]

        outstanding_payments = Payment.objects.filter(amount_paid__lt=F("amount_due")).aggregate(
            total=Sum(F("amount_due") - F("amount_paid"))
        )["total"] or 0

        context.update(
            {
                "stats": {
                    "students": active_students.count(),
                    "teachers": active_teachers.count(),
                    "courses": active_courses.count(),
                    "active_enrollments": Enrollment.objects.filter(status=Enrollment.Status.ACTIVE).count(),
                    "outstanding_payments": outstanding_payments,
                },
                "top_students": top_students,
                "risky_students": risky_students,
                "teacher_ranking": teacher_ranking,
            }
        )
        return context


class StudentListView(LoginRequiredMixin, ListView):
    model = Student
    template_name = "crm/students/list.html"
    context_object_name = "students"
    paginate_by = 20

    def get_queryset(self):
        queryset = Student.objects.filter(is_active=True).prefetch_related("enrollments__course")
        for student in queryset:
            ScoringService.recalculate_student_score(student)
        return queryset


class StudentDetailView(LoginRequiredMixin, DetailView):
    model = Student
    template_name = "crm/students/detail.html"
    context_object_name = "student"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        student = self.object
        score = ScoringService.recalculate_student_score(student)
        enrollments = student.enrollments.select_related("course", "course__teacher")
        recent_attendance = student.attendance_records.select_related("lesson", "lesson__course")[:10]
        recent_grades = student.grades.select_related("lesson", "lesson__course")[:10]
        payments = student.payments.all()[:12]

        context.update(
            {
                "score": score,
                "enrollments": enrollments,
                "recent_attendance": recent_attendance,
                "recent_grades": recent_grades,
                "payments": payments,
            }
        )
        return context


class TeacherListView(LoginRequiredMixin, ListView):
    model = Teacher
    template_name = "crm/teachers/list.html"
    context_object_name = "teachers"
    paginate_by = 20

    def get_queryset(self):
        queryset = Teacher.objects.filter(is_active=True).prefetch_related("courses")
        for teacher in queryset:
            ScoringService.recalculate_teacher_score(teacher)
        return queryset


class TeacherDetailView(LoginRequiredMixin, DetailView):
    model = Teacher
    template_name = "crm/teachers/detail.html"
    context_object_name = "teacher"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        teacher = self.object
        score = ScoringService.recalculate_teacher_score(teacher)
        courses = teacher.courses.prefetch_related("enrollments", "lessons")
        students = ScoringService.teacher_students_queryset(teacher).select_related("score")

        context.update(
            {
                "score": score,
                "courses": courses,
                "students": students,
            }
        )
        return context


class CourseListView(LoginRequiredMixin, ListView):
    model = Course
    template_name = "crm/courses/list.html"
    context_object_name = "courses"

    def get_queryset(self):
        return Course.objects.select_related("teacher").annotate(
            active_students=Count("enrollments", filter=Q(enrollments__status=Enrollment.Status.ACTIVE))
        )


class CourseDetailView(LoginRequiredMixin, DetailView):
    model = Course
    template_name = "crm/courses/detail.html"
    context_object_name = "course"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        course = self.object
        for enrollment in course.enrollments.select_related("student"):
            ScoringService.recalculate_student_score(enrollment.student)
        enrollments = course.enrollments.select_related("student")
        lessons = course.lessons.all()[:20]
        teacher_score = ScoringService.recalculate_teacher_score(course.teacher)

        context.update(
            {
                "enrollments": enrollments,
                "lessons": lessons,
                "teacher_score": teacher_score,
            }
        )
        return context


class AnalyticsOverviewView(LoginRequiredMixin, TemplateView):
    template_name = "crm/analytics/overview.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        students = Student.objects.filter(is_active=True)
        teachers = Teacher.objects.filter(is_active=True)
        for student in students:
            ScoringService.recalculate_student_score(student)
        for teacher in teachers:
            ScoringService.recalculate_teacher_score(teacher)

        context.update(
            {
                "top_students": StudentScore.objects.select_related("student").order_by("-total_score")[:10],
                "risky_students": StudentScore.objects.select_related("student").filter(
                    risk_level=StudentScore.RiskLevel.HIGH
                )[:10],
                "teacher_ranking": TeacherScore.objects.select_related("teacher").order_by("-total_score")[:10],
                "risk_distribution": StudentScore.objects.values("risk_level").annotate(total=Count("id")),
                "avg_student_score": StudentScore.objects.aggregate(value=Avg("total_score"))["value"] or 0,
                "avg_teacher_score": TeacherScore.objects.aggregate(value=Avg("total_score"))["value"] or 0,
                "student_ml_model": load_model_artifact("student"),
                "teacher_ml_model": load_model_artifact("teacher"),
                "ml_blended_students": StudentScore.objects.filter(score_source=StudentScore.ScoreSource.ML_BLENDED).count(),
                "ml_blended_teachers": TeacherScore.objects.filter(score_source=TeacherScore.ScoreSource.ML_BLENDED).count(),
            }
        )
        return context
