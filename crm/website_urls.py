from django.urls import path

from .views import (
    AnalyticsOverviewView,
    CourseDetailView,
    CourseListView,
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
    path("analytics/", AnalyticsOverviewView.as_view(), name="analytics-overview"),
]
