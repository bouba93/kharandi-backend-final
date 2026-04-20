from django.urls import path
from .views import KaramoAskView, KaramoQuotaView, ConversationListView, ConversationDetailView
urlpatterns = [
    path("ask/",                                KaramoAskView.as_view(),          name="ai-ask"),
    path("quota/",                              KaramoQuotaView.as_view(),        name="ai-quota"),
    path("conversations/",                      ConversationListView.as_view(),   name="ai-conversations"),
    path("conversations/<int:conversation_id>/",ConversationDetailView.as_view(), name="ai-conv-detail"),
]
