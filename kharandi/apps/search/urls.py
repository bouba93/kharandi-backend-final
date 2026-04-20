from django.urls import path
from .views import GlobalSearchView, SearchSuggestionsView
urlpatterns = [
    path("",         GlobalSearchView.as_view(),      name="search"),
    path("suggest/", SearchSuggestionsView.as_view(), name="search-suggest"),
]
