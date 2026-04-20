"""
Recherche sans django.contrib.postgres — compatible Python 3.14 / Render
Utilise icontains + Q objects avec score de pertinence simple.
"""
from django.db.models import Q, F, Value, Case, When, IntegerField
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny


class GlobalSearchView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        query = request.query_params.get("q", "").strip()
        stype = request.query_params.get("type", "all")
        limit = min(int(request.query_params.get("limit", 20)), 100)

        if not query or len(query) < 2:
            return Response({"success": False, "message": "'q' doit faire au moins 2 caractères."}, status=400)

        results = {}
        if stype in ("all", "courses"):  results["courses"]  = _search_courses(query, limit)
        if stype in ("all", "products"): results["products"] = _search_products(query, limit)
        if stype in ("all", "tutors"):   results["tutors"]   = _search_tutors(query, limit)

        total = sum(len(v) for v in results.values())
        return Response({"success": True, "message": f"{total} résultat(s).",
                         "data": {"query": query, "results": results, "total": total}})


def _search_courses(query, limit):
    from kharandi.apps.courses.models import Course
    qs = Course.objects.filter(
        Q(title__icontains=query) | Q(subject__icontains=query) |
        Q(tags__icontains=query)  | Q(description__icontains=query) |
        Q(tutor__first_name__icontains=query) | Q(tutor__last_name__icontains=query),
        status="active"
    ).annotate(
        relevance=Case(
            When(title__icontains=query,   then=Value(3)),
            When(subject__icontains=query, then=Value(2)),
            default=Value(1), output_field=IntegerField(),
        )
    ).order_by("-relevance", "-students_count").distinct()
    return list(qs.values("id","title","subject","level","price","is_free",
                          "avg_rating","students_count","relevance",
                          tutor_name=F("tutor__first_name"),
                          tutor_city=F("tutor__city"))[:limit])


def _search_products(query, limit):
    from kharandi.apps.marketplace.models import Product
    qs = Product.objects.filter(
        Q(name__icontains=query) | Q(description__icontains=query) |
        Q(tags__icontains=query) | Q(category__name__icontains=query),
        status="active"
    ).annotate(
        relevance=Case(
            When(name__icontains=query, then=Value(3)),
            When(tags__icontains=query, then=Value(2)),
            default=Value(1), output_field=IntegerField(),
        )
    ).order_by("-relevance", "-avg_rating").distinct()
    return list(qs.values("id","name","price","avg_rating","reviews_count","relevance",
                          vendor_name=F("vendor__vendor_profile__shop_name"),
                          category_name=F("category__name"))[:limit])


def _search_tutors(query, limit):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    qs = User.objects.filter(
        Q(first_name__icontains=query) | Q(last_name__icontains=query) |
        Q(tutor_profile__subjects__icontains=query) | Q(city__icontains=query),
        role="tutor", status="active",
    ).distinct()
    return list(qs.values("id","first_name","last_name","city",
                          subjects=F("tutor_profile__subjects"),
                          avg_rating=F("tutor_profile__avg_rating"),
                          price=F("tutor_profile__price_per_hour"))[:limit])


class SearchSuggestionsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        query = request.query_params.get("q", "").strip()
        if not query or len(query) < 2:
            return Response({"success": True, "data": []})
        from kharandi.apps.courses.models import Course
        from kharandi.apps.marketplace.models import Product
        suggestions  = [{"type":"course",  "text":t} for t in Course.objects.filter(title__icontains=query, status="active").values_list("title",flat=True)[:4]]
        suggestions += [{"type":"product", "text":n} for n in Product.objects.filter(name__icontains=query,  status="active").values_list("name", flat=True)[:4]]
        return Response({"success": True, "data": suggestions[:8]})
