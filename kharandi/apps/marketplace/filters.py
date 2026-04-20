import django_filters
from .models import Product

class ProductFilter(django_filters.FilterSet):
    min_price   = django_filters.NumberFilter(field_name="price", lookup_expr="gte")
    max_price   = django_filters.NumberFilter(field_name="price", lookup_expr="lte")
    min_rating  = django_filters.NumberFilter(field_name="avg_rating", lookup_expr="gte")
    category    = django_filters.CharFilter(field_name="category__slug")
    vendor_city = django_filters.CharFilter(field_name="vendor__city")
    has_stock   = django_filters.BooleanFilter(method="filter_has_stock")

    class Meta:
        model  = Product
        fields = ["category", "vendor", "min_price", "max_price", "min_rating"]

    def filter_has_stock(self, qs, name, value):
        if value:
            return qs.filter(variants__stock__gt=0).distinct()
        return qs
