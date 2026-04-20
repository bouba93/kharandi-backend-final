from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework_simplejwt.views import TokenRefreshView
from kharandi.apps.accounts.views import HealthCheckView

urlpatterns = [
    path("admin/",                   admin.site.urls),
    path("",                         HealthCheckView.as_view(), name="health"),
    path("api/health/",              HealthCheckView.as_view(), name="health-api"),

    # Auth & utilisateurs
    path("api/auth/",                include("kharandi.apps.accounts.urls")),
    path("api/auth/token/refresh/",  TokenRefreshView.as_view(), name="token_refresh"),

    # Modules métier
    path("api/marketplace/",         include("kharandi.apps.marketplace.urls")),
    path("api/payments/",            include("kharandi.apps.payments.urls")),
    path("api/courses/",             include("kharandi.apps.courses.urls")),
    path("api/notify/",              include("kharandi.apps.notifications.urls")),
    path("api/search/",              include("kharandi.apps.search.urls")),
    path("api/reports/",             include("kharandi.apps.reports.urls")),
    path("api/support/",             include("kharandi.apps.support.urls")),
    path("api/ai/",                  include("kharandi.apps.ai_assistant.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
