from django.urls import path

from .views import RiskyStudentsView, StudentScoreDetailView, TeacherRankingView, TeacherScoreDetailView, TopStudentsView


urlpatterns = [
    path("students/<int:pk>/score", StudentScoreDetailView.as_view(), name="student-score"),
    path("teachers/<int:pk>/score", TeacherScoreDetailView.as_view(), name="teacher-score"),
    path("analytics/top-students", TopStudentsView.as_view(), name="top-students"),
    path("analytics/risky-students", RiskyStudentsView.as_view(), name="risky-students"),
    path("analytics/teacher-ranking", TeacherRankingView.as_view(), name="teacher-ranking"),
]
