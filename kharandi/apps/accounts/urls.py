from django.urls import path
from rest_framework_simplejwt.views import TokenBlacklistView
from .views import (
    RegisterView, LoginView, LogoutView,
    OTPSendView, OTPVerifyView, OTPResendView,
    PasswordResetRequestView, PasswordResetConfirmView,
    UserProfileView, TutorProfileView, VendorProfileView,
    TutorListView,
)

urlpatterns = [
    path("register/",              RegisterView.as_view(),             name="register"),
    path("login/",                 LoginView.as_view(),                name="login"),
    path("logout/",                LogoutView.as_view(),               name="logout"),
    path("token/blacklist/",       TokenBlacklistView.as_view(),       name="token_blacklist"),

    path("otp/send/",              OTPSendView.as_view(),              name="otp-send"),
    path("otp/verify/",            OTPVerifyView.as_view(),            name="otp-verify"),
    path("otp/resend/",            OTPResendView.as_view(),            name="otp-resend"),

    path("password/reset/",        PasswordResetRequestView.as_view(), name="password-reset"),
    path("password/reset/confirm/",PasswordResetConfirmView.as_view(), name="password-reset-confirm"),

    path("profile/",               UserProfileView.as_view(),          name="user-profile"),
    path("profile/tutor/",         TutorProfileView.as_view(),         name="tutor-profile"),
    path("profile/vendor/",        VendorProfileView.as_view(),        name="vendor-profile"),
    path("tutors/",                TutorListView.as_view(),            name="tutor-list"),
]

# Endpoint cron (appelable par cron-job.org ou similaire)
from kharandi.apps.accounts.cron_views import CronInactivityView, CronCleanupOTPView
urlpatterns += [
    path("admin/cron/inactivity/", CronInactivityView.as_view(), name="cron-inactivity"),
    path("admin/cron/cleanup-otp/", CronCleanupOTPView.as_view(), name="cron-cleanup-otp"),
]
