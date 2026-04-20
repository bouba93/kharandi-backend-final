from django.urls import path
from .generators import TransactionsPDFView, StudentBulletinPDFView, StatsExcelView, MyTransactionsPDFView
urlpatterns = [
    path("transactions/pdf/",   TransactionsPDFView.as_view(),   name="report-transactions-pdf"),
    path("bulletin/pdf/",       StudentBulletinPDFView.as_view(),name="report-bulletin-pdf"),
    path("stats/excel/",        StatsExcelView.as_view(),         name="report-stats-excel"),
    path("my-transactions/pdf/",MyTransactionsPDFView.as_view(), name="my-transactions-pdf"),
]
