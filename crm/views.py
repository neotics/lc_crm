from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.db.models import Avg, Count, DecimalField, ExpressionWrapper, F, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.generic import DetailView, ListView, TemplateView
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from .ml import load_model_artifact
from .models import Attendance, Course, Enrollment, Grade, Lesson, Payment, Student, StudentScore, Teacher, TeacherScore
from .roles import (
    filter_courses_for_user,
    filter_students_for_user,
    filter_teachers_for_user,
    get_teacher_profile,
    has_crm_access,
    is_admin_user,
)
from .serializers import StudentScoreSerializer, TeacherScoreSerializer
from .services import ScoringService


class RoleAwareLoginView(LoginView):
    template_name = "auth/login.html"
    redirect_authenticated_user = True


class CRMAccessMixin(LoginRequiredMixin):
    teacher_profile = None
    is_admin_area_user = False

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not has_crm_access(request.user):
            raise PermissionDenied("This user is not linked to a CRM role.")

        self.teacher_profile = get_teacher_profile(request.user)
        self.is_admin_area_user = is_admin_user(request.user)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "current_teacher": self.teacher_profile,
                "is_admin_user": self.is_admin_area_user,
                "teacher_mode": bool(self.teacher_profile and not self.is_admin_area_user),
            }
        )
        return context


class AdminRequiredMixin(CRMAccessMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not is_admin_user(request.user):
            raise PermissionDenied("Only admin users can open this page.")
        return super().dispatch(request, *args, **kwargs)


def user_can_access_student(user, student: Student) -> bool:
    if is_admin_user(user):
        return True

    teacher = get_teacher_profile(user)
    if not teacher:
        return False

    return Student.objects.filter(pk=student.pk, enrollments__course__teacher=teacher).exists()


def user_can_access_teacher(user, teacher: Teacher) -> bool:
    if is_admin_user(user):
        return True

    teacher_profile = get_teacher_profile(user)
    return bool(teacher_profile and teacher_profile.pk == teacher.pk)


class StudentScoreDetailView(APIView):
    def get(self, request, pk: int):
        student = get_object_or_404(Student, pk=pk)
        if not user_can_access_student(request.user, student):
            raise PermissionDenied("You do not have access to this student.")
        score = ScoringService.recalculate_student_score(student)
        return Response(StudentScoreSerializer(score).data)


class TeacherScoreDetailView(APIView):
    def get(self, request, pk: int):
        teacher = get_object_or_404(Teacher, pk=pk)
        if not user_can_access_teacher(request.user, teacher):
            raise PermissionDenied("You do not have access to this teacher.")
        score = ScoringService.recalculate_teacher_score(teacher)
        return Response(TeacherScoreSerializer(score).data)


class TopStudentsView(generics.ListAPIView):
    serializer_class = StudentScoreSerializer

    def get_queryset(self):
        students = filter_students_for_user(Student.objects.filter(is_active=True), self.request.user)
        return StudentScore.objects.select_related("student").filter(student__in=students).order_by("-total_score")[:10]


class RiskyStudentsView(generics.ListAPIView):
    serializer_class = StudentScoreSerializer

    def get_queryset(self):
        students = filter_students_for_user(Student.objects.filter(is_active=True), self.request.user)
        return StudentScore.objects.select_related("student").filter(
            student__in=students,
            risk_level=StudentScore.RiskLevel.HIGH,
        ).order_by("total_score")


class TeacherRankingView(generics.ListAPIView):
    serializer_class = TeacherScoreSerializer

    def get_queryset(self):
        teachers = filter_teachers_for_user(Teacher.objects.filter(is_active=True), self.request.user)
        return TeacherScore.objects.select_related("teacher").filter(teacher__in=teachers).order_by("-total_score")


class AuthDiagnosticsView(APIView):
    permission_classes = []
    authentication_classes = []

    def get(self, request):
        token = request.GET.get("token", "")
        if not settings.DIAGNOSTIC_TOKEN or token != settings.DIAGNOSTIC_TOKEN:
            return Response({"detail": "Forbidden"}, status=403)

        username = request.GET.get("username", "")
        password = request.GET.get("password", "")
        User = get_user_model()
        user = User.objects.filter(username=username).first() if username else None
        authenticated = authenticate(username=username, password=password) if username and password else None

        database_name = connection.settings_dict.get("NAME")
        database_host = connection.settings_dict.get("HOST")

        return Response(
            {
                "database_engine": connection.settings_dict.get("ENGINE"),
                "database_name": str(database_name),
                "database_host": database_host,
                "user_count": User.objects.count(),
                "username_checked": username,
                "user_exists": bool(user),
                "is_active": bool(user.is_active) if user else False,
                "is_staff": bool(user.is_staff) if user else False,
                "is_superuser": bool(user.is_superuser) if user else False,
                "has_teacher_profile": bool(get_teacher_profile(user)) if user else False,
                "password_check": user.check_password(password) if user and password else None,
                "authenticate_result": bool(authenticated),
            }
        )


class DashboardView(CRMAccessMixin, TemplateView):
    template_name = "crm/dashboard.html"

    @staticmethod
    def calculate_outstanding_payments(student_queryset=None):
        debt_expression = ExpressionWrapper(
            F("amount_due") - F("amount_paid"),
            output_field=DecimalField(max_digits=10, decimal_places=2),
        )
        payments = Payment.objects.filter(amount_paid__lt=F("amount_due"))
        if student_queryset is not None:
            payments = payments.filter(student__in=student_queryset)

        return payments.aggregate(
            total=Coalesce(
                Sum(debt_expression),
                Value(0),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
        ).get("total")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        active_students = filter_students_for_user(Student.objects.filter(is_active=True), self.request.user)
        active_teachers = filter_teachers_for_user(Teacher.objects.filter(is_active=True), self.request.user)
        active_courses = filter_courses_for_user(Course.objects.filter(is_active=True), self.request.user)

        top_students = StudentScore.objects.select_related("student").filter(student__in=active_students).order_by("-total_score")[
            :10
        ]
        risky_students = StudentScore.objects.select_related("student").filter(
            student__in=active_students,
            risk_level=StudentScore.RiskLevel.HIGH
        )[:10]
        teacher_ranking = TeacherScore.objects.select_related("teacher").filter(teacher__in=active_teachers).order_by(
            "-total_score"
        )[:10]

        outstanding_payments = self.calculate_outstanding_payments(student_queryset=active_students)
        active_enrollments = Enrollment.objects.filter(
            status=Enrollment.Status.ACTIVE,
            course__in=active_courses,
        ).count()

        context.update(
            {
                "stats": {
                    "students": active_students.count(),
                    "teachers": active_teachers.count(),
                    "courses": active_courses.count(),
                    "active_enrollments": active_enrollments,
                    "outstanding_payments": outstanding_payments,
                },
                "top_students": top_students,
                "risky_students": risky_students,
                "teacher_ranking": teacher_ranking,
            }
        )
        return context


class StudentListView(CRMAccessMixin, ListView):
    model = Student
    template_name = "crm/students/list.html"
    context_object_name = "students"
    paginate_by = 20

    def get_queryset(self):
        queryset = Student.objects.filter(is_active=True).select_related("score").prefetch_related("enrollments__course")
        return filter_students_for_user(queryset, self.request.user)


class StudentDetailView(CRMAccessMixin, DetailView):
    model = Student
    template_name = "crm/students/detail.html"
    context_object_name = "student"

    def get_queryset(self):
        queryset = Student.objects.select_related("score").prefetch_related("enrollments__course")
        return filter_students_for_user(queryset, self.request.user)

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


class TeacherListView(CRMAccessMixin, ListView):
    model = Teacher
    template_name = "crm/teachers/list.html"
    context_object_name = "teachers"
    paginate_by = 20

    def get_queryset(self):
        queryset = Teacher.objects.filter(is_active=True).select_related("score", "user").prefetch_related("courses")
        return filter_teachers_for_user(queryset, self.request.user)


class TeacherDetailView(CRMAccessMixin, DetailView):
    model = Teacher
    template_name = "crm/teachers/detail.html"
    context_object_name = "teacher"

    def get_queryset(self):
        queryset = Teacher.objects.select_related("score", "user").prefetch_related("courses")
        return filter_teachers_for_user(queryset, self.request.user)

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


class CourseListView(CRMAccessMixin, ListView):
    model = Course
    template_name = "crm/courses/list.html"
    context_object_name = "courses"

    def get_queryset(self):
        queryset = Course.objects.select_related("teacher").annotate(
            active_students=Count("enrollments", filter=Q(enrollments__status=Enrollment.Status.ACTIVE))
        )
        return filter_courses_for_user(queryset, self.request.user)


class CourseDetailView(CRMAccessMixin, DetailView):
    model = Course
    template_name = "crm/courses/detail.html"
    context_object_name = "course"

    def get_queryset(self):
        queryset = Course.objects.select_related("teacher").prefetch_related("enrollments__student", "lessons")
        return filter_courses_for_user(queryset, self.request.user)

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


class LessonRecordView(CRMAccessMixin, TemplateView):
    template_name = "crm/lessons/record.html"

    def get_course(self):
        queryset = filter_courses_for_user(Course.objects.select_related("teacher"), self.request.user)
        return get_object_or_404(queryset, pk=self.kwargs["course_pk"])

    def get_lesson(self, course):
        lesson_pk = self.kwargs.get("lesson_pk")
        if not lesson_pk:
            return None
        return get_object_or_404(Lesson.objects.filter(course=course), pk=lesson_pk)

    def get_enrollments(self, course):
        return course.enrollments.filter(status=Enrollment.Status.ACTIVE).select_related("student").order_by(
            "student__full_name"
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        course = kwargs.get("course") or self.get_course()
        lesson = kwargs.get("lesson")
        if lesson is None and "lesson" not in kwargs:
            lesson = self.get_lesson(course)
        rows = kwargs.get("rows") or self.build_rows(course, lesson)
        context.update(
            {
                "course": course,
                "lesson": lesson,
                "lesson_date": self.format_lesson_date(
                    kwargs.get("lesson_date") or (lesson.date if lesson else timezone.localdate())
                ),
                "topic": kwargs.get("topic") if "topic" in kwargs else (lesson.topic if lesson else ""),
                "rows": rows,
                "status_choices": Attendance.Status.choices,
                "participation_choices": Attendance.Participation.choices,
                "form_errors": kwargs.get("form_errors", []),
            }
        )
        return context

    @staticmethod
    def format_lesson_date(value):
        return value.isoformat() if hasattr(value, "isoformat") else value

    def build_rows(self, course, lesson):
        attendance_by_student = {}
        grade_by_student = {}
        if lesson:
            attendance_by_student = {
                item.student_id: item for item in lesson.attendance_records.select_related("student")
            }
            grade_by_student = {item.student_id: item for item in lesson.grades.select_related("student")}

        rows = []
        for enrollment in self.get_enrollments(course):
            student = enrollment.student
            attendance = attendance_by_student.get(student.pk)
            grade = grade_by_student.get(student.pk)
            rows.append(
                {
                    "student": student,
                    "status": attendance.status if attendance else Attendance.Status.PRESENT,
                    "participation": attendance.participation if attendance else Attendance.Participation.MEDIUM,
                    "grade": grade.grade if grade else "",
                }
            )
        return rows

    def post(self, request, *args, **kwargs):
        course = self.get_course()
        lesson = self.get_lesson(course)
        enrollments = list(self.get_enrollments(course))

        lesson_date = parse_date(request.POST.get("lesson_date", ""))
        topic = request.POST.get("topic", "").strip()
        form_errors = []
        rows = []
        valid_statuses = {value for value, _label in Attendance.Status.choices}
        valid_participation = {value for value, _label in Attendance.Participation.choices}

        if lesson_date is None:
            form_errors.append("Dars sanasini YYYY-MM-DD formatida kiriting.")

        for enrollment in enrollments:
            student = enrollment.student
            status = request.POST.get(f"status_{student.pk}", Attendance.Status.PRESENT)
            participation = request.POST.get(f"participation_{student.pk}", Attendance.Participation.MEDIUM)
            grade_value = request.POST.get(f"grade_{student.pk}", "").strip()

            if status not in valid_statuses:
                form_errors.append(f"{student.full_name}: attendance status noto'g'ri.")
                status = Attendance.Status.PRESENT

            if status == Attendance.Status.ABSENT:
                participation = Attendance.Participation.NONE
                grade_value = ""
            elif participation not in valid_participation:
                form_errors.append(f"{student.full_name}: aktivlik darajasi noto'g'ri.")
                participation = Attendance.Participation.MEDIUM

            grade = None
            if grade_value:
                try:
                    grade = float(grade_value)
                except ValueError:
                    form_errors.append(f"{student.full_name}: baho raqam bo'lishi kerak.")
                else:
                    if grade < 0 or grade > 100:
                        form_errors.append(f"{student.full_name}: baho 0 dan 100 gacha bo'lishi kerak.")

            rows.append(
                {
                    "student": student,
                    "status": status,
                    "participation": participation,
                    "grade": grade_value,
                    "parsed_grade": grade,
                }
            )

        if form_errors:
            context = self.get_context_data(
                course=course,
                lesson=lesson,
                lesson_date=request.POST.get("lesson_date", ""),
                topic=topic,
                rows=rows,
                form_errors=form_errors,
            )
            return self.render_to_response(context, status=400)

        if lesson is None:
            lesson = Lesson.objects.create(course=course, date=lesson_date, topic=topic)
        else:
            lesson.date = lesson_date
            lesson.topic = topic
            lesson.save(update_fields=["date", "topic", "updated_at"])

        for row in rows:
            student = row["student"]
            Attendance.objects.update_or_create(
                lesson=lesson,
                student=student,
                defaults={
                    "status": row["status"],
                    "participation": row["participation"],
                },
            )

            if row["parsed_grade"] is None:
                Grade.objects.filter(lesson=lesson, student=student).delete()
            else:
                grade_queryset = Grade.objects.filter(lesson=lesson, student=student).order_by("pk")
                grade = grade_queryset.first()
                if grade:
                    grade.grade = row["parsed_grade"]
                    grade.save(update_fields=["grade", "updated_at"])
                    grade_queryset.exclude(pk=grade.pk).delete()
                else:
                    Grade.objects.create(lesson=lesson, student=student, grade=row["parsed_grade"])

        ScoringService.recalculate_students([row["student"] for row in rows])
        ScoringService.recalculate_teacher_score(course.teacher)
        messages.success(request, "Dars, attendance, aktivlik va baholar saqlandi.")
        return redirect("course-detail", pk=course.pk)


class AnalyticsOverviewView(AdminRequiredMixin, TemplateView):
    template_name = "crm/analytics/overview.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        students = Student.objects.filter(is_active=True)
        teachers = Teacher.objects.filter(is_active=True)

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
