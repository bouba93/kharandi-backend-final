from django.urls import path
from .views import InitiatePaymentView, PaymentCallbackView, TransactionListView, InvoiceDownloadView, SMSBalanceView
urlpatterns = [
    path("initiate/",          InitiatePaymentView.as_view(),  name="payment-initiate"),
    path("callback/",          PaymentCallbackView.as_view(),  name="payment-callback"),
    path("transactions/",      TransactionListView.as_view(),  name="transaction-list"),
    path("invoice/<int:pk>/",  InvoiceDownloadView.as_view(),  name="invoice-download"),
    path("sms-balance/",       SMSBalanceView.as_view(),       name="sms-balance"),
]
