from django.urls import path
from .views import TicketListCreateView, TicketDetailView, TicketResolveView, TicketAssignView
urlpatterns = [
    path("tickets/",               TicketListCreateView.as_view(), name="ticket-list"),
    path("tickets/<int:pk>/",      TicketDetailView.as_view(),     name="ticket-detail"),
    path("tickets/<int:pk>/resolve/", TicketResolveView.as_view(), name="ticket-resolve"),
    path("tickets/<int:pk>/assign/",  TicketAssignView.as_view(),  name="ticket-assign"),
]
