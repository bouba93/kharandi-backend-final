from django.urls import path
from .views import (
    WelcomeSMSView, OrderConfirmationSMSView, OrderShippedSMSView, OrderDeliveredSMSView,
    PointsSMSView, NewMessageSMSView, CourseReminderSMSView, AnnonceValidatedSMSView,
    AccountSuspendedSMSView, PasswordResetSMSView, NewStudentSMSView,
    BulkSMSView, CustomSMSView, SMSBalanceView,
)
urlpatterns = [
    path("welcome/",           WelcomeSMSView.as_view(),           name="sms-welcome"),
    path("order-confirm/",     OrderConfirmationSMSView.as_view(), name="sms-order-confirm"),
    path("order-shipped/",     OrderShippedSMSView.as_view(),      name="sms-order-shipped"),
    path("order-delivered/",   OrderDeliveredSMSView.as_view(),    name="sms-order-delivered"),
    path("points/",            PointsSMSView.as_view(),            name="sms-points"),
    path("new-message/",       NewMessageSMSView.as_view(),        name="sms-new-message"),
    path("course-reminder/",   CourseReminderSMSView.as_view(),    name="sms-course-reminder"),
    path("annonce-validated/", AnnonceValidatedSMSView.as_view(),  name="sms-annonce-validated"),
    path("account-suspended/", AccountSuspendedSMSView.as_view(),  name="sms-account-suspended"),
    path("password-reset/",    PasswordResetSMSView.as_view(),     name="sms-password-reset"),
    path("new-student/",       NewStudentSMSView.as_view(),        name="sms-new-student"),
    path("bulk/",              BulkSMSView.as_view(),              name="sms-bulk"),
    path("custom/",            CustomSMSView.as_view(),            name="sms-custom"),
    path("balance/",           SMSBalanceView.as_view(),           name="sms-balance"),
]
