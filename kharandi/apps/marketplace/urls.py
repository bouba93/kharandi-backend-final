from django.urls import path
from .views import (
    ProductListCreateView, ProductDetailView, ProductValidateView,
    MyProductsView, ProductReviewCreateView, CartCheckoutView,
    OrderListCreateView, OrderDetailView, CategoryListView,
)
urlpatterns = [
    path("categories/",                 CategoryListView.as_view(),         name="categories"),
    path("products/",                   ProductListCreateView.as_view(),    name="product-list"),
    path("products/<int:pk>/",          ProductDetailView.as_view(),        name="product-detail"),
    path("products/<int:pk>/validate/", ProductValidateView.as_view(),      name="product-validate"),
    path("products/<int:pk>/review/",   ProductReviewCreateView.as_view(),  name="product-review"),
    path("my-products/",                MyProductsView.as_view(),           name="my-products"),
    path("orders/",                     OrderListCreateView.as_view(),      name="order-list"),
    path("orders/<int:pk>/",            OrderDetailView.as_view(),          name="order-detail"),
    path("checkout/",                   CartCheckoutView.as_view(),         name="checkout"),
]
