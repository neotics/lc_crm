from django.urls import path

from .views import (
    AnalyticsOverviewView,
    CourseDetailView,
    CourseListView,
    LessonRecordView,
    StudentDetailView,
    StudentListView,
    TeacherDetailView,
    TeacherListView,
)


urlpatterns = [
    path("students/", StudentListView.as_view(), name="student-list"),
    path("students/<int:pk>/", StudentDetailView.as_view(), name="student-detail"),
    path("teachers/", TeacherListView.as_view(), name="teacher-list"),
    path("teachers/<int:pk>/", TeacherDetailView.as_view(), name="teacher-detail"),
    path("courses/", CourseListView.as_view(), name="course-list"),
    path("courses/<int:pk>/", CourseDetailView.as_view(), name="course-detail"),
    path("courses/<int:course_pk>/lessons/new/", LessonRecordView.as_view(), name="lesson-record-create"),
    path(
        "courses/<int:course_pk>/lessons/<int:lesson_pk>/records/",
        LessonRecordView.as_view(),
        name="lesson-record-edit",
    ),
    path("analytics/", AnalyticsOverviewView.as_view(), name="analytics-overview"),
]
