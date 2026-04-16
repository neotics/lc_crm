from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from crm.admin import analytics_dashboard_view
from crm.views import DashboardView, RoleAwareLoginView


urlpatterns = [
    path("", DashboardView.as_view(), name="dashboard"),
    path("login/", RoleAwareLoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("admin/analytics-dashboard/", admin.site.admin_view(analytics_dashboard_view), name="analytics-dashboard"),
    path("", include("crm.website_urls")),
    path("admin/", admin.site.urls),
    path("api/", include("crm.urls")),
]
