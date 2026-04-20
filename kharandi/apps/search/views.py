"""
╔══════════════════════════════════════════════════════════════════════════╗
║           KHARANDI — Recherche Full-Text PostgreSQL                     ║
╚══════════════════════════════════════════════════════════════════════════╝
"""

from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank, TrigramSimilarity
from django.db.models import Q, F
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny


class GlobalSearchView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        query = request.query_params.get("q", "").strip()
        stype = request.query_params.get("type", "all")   # all | courses | products | tutors
        limit = min(int(request.query_params.get("limit", 20)), 100)

        if not query or len(query) < 2:
            return Response(
                {"success": False, "message": "'q' doit faire au moins 2 caractères."},
                status=400
            )

        results = {}

        if stype in ("all", "courses"):
            results["courses"] = _search_courses(query, limit)

        if stype in ("all", "products"):
            results["products"] = _search_products(query, limit)

        if stype in ("all", "tutors"):
            results["tutors"] = _search_tutors(query, limit)

        total = sum(len(v) for v in results.values())
        return Response({
            "success": True,
            "message": f"{total} résultat(s) pour '{query}'.",
            "data":    {"query": query, "results": results, "total": total},
        })


def _search_courses(query: str, limit: int) -> list:
    from kharandi.apps.courses.models import Course
    sq = SearchQuery(query, config="french")
    sv = (
        SearchVector("title",       weight="A", config="french") +
        SearchVector("subject",     weight="B", config="french") +
        SearchVector("description", weight="C", config="french") +
        SearchVector("tags",        weight="D", config="french")
    )
    qs = Course.objects.filter(status="active").annotate(rank=SearchRank(sv, sq)).filter(
        rank__gte=0.01
    ).order_by("-rank").values(
        "id", "title", "subject", "level", "price", "is_free",
        "avg_rating", "students_count", "rank",
        tutor_name=F("tutor__first_name"),
    )[:limit]

    result = list(qs)
    if not result:
        # Fallback icontains
        result = list(Course.objects.filter(
            Q(title__icontains=query) | Q(subject__icontains=query) | Q(tags__icontains=query),
            status="active"
        ).values("id","title","subject","level","price","is_free","avg_rating","students_count",
                 tutor_name=F("tutor__first_name"))[:limit])
    return result


def _search_products(query: str, limit: int) -> list:
    from kharandi.apps.marketplace.models import Product
    sq = SearchQuery(query, config="french")
    sv = (
        SearchVector("name",        weight="A", config="french") +
        SearchVector("description", weight="B", config="french") +
        SearchVector("tags",        weight="C", config="french")
    )
    qs = Product.objects.filter(status="active").annotate(rank=SearchRank(sv, sq)).filter(
        rank__gte=0.01
    ).order_by("-rank").values(
        "id","name","price","avg_rating","reviews_count","rank",
        vendor_name=F("vendor__vendor_profile__shop_name"),
        category_name=F("category__name"),
    )[:limit]

    result = list(qs)
    if not result:
        result = list(Product.objects.filter(
            Q(name__icontains=query) | Q(description__icontains=query),
            status="active"
        ).values("id","name","price","avg_rating","reviews_count",
                 vendor_name=F("vendor__vendor_profile__shop_name"),
                 category_name=F("category__name"))[:limit])
    return result


def _search_tutors(query: str, limit: int) -> list:
    from django.contrib.auth import get_user_model
    User = get_user_model()
    qs = User.objects.filter(
        role="tutor", status="active", tutor_profile__is_kyc_verified=True
    ).annotate(
        sim=TrigramSimilarity("first_name", query) + TrigramSimilarity("last_name", query)
    ).filter(sim__gte=0.1).order_by("-sim").values(
        "id","first_name","last_name","city",
        subjects=F("tutor_profile__subjects"),
        avg_rating=F("tutor_profile__avg_rating"),
        price=F("tutor_profile__price_per_hour"),
    )[:limit]

    result = list(qs)
    if not result:
        result = list(User.objects.filter(
            Q(first_name__icontains=query) | Q(last_name__icontains=query) |
            Q(tutor_profile__subjects__icontains=query),
            role="tutor", status="active"
        ).values("id","first_name","last_name","city",
                 subjects=F("tutor_profile__subjects"),
                 avg_rating=F("tutor_profile__avg_rating"),
                 price=F("tutor_profile__price_per_hour"))[:limit])
    return result


class SearchSuggestionsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        query = request.query_params.get("q", "").strip()
        if not query or len(query) < 2:
            return Response({"success": True, "data": []})

        from kharandi.apps.courses.models import Course
        from kharandi.apps.marketplace.models import Product

        suggestions = []
        courses  = Course.objects.filter(title__icontains=query, status="active").values_list("title", flat=True)[:4]
        products = Product.objects.filter(name__icontains=query, status="active").values_list("name", flat=True)[:4]

        suggestions += [{"type": "course",   "text": t} for t in courses]
        suggestions += [{"type": "product",  "text": n} for n in products]

        return Response({"success": True, "data": suggestions[:8]})
