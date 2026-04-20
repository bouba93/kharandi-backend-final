import logging
from django.db import transaction
from django.db.models import F
from django.conf import settings
from django.utils import timezone
from rest_framework import generics, status, filters
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from django_filters.rest_framework import DjangoFilterBackend

from .models import Product, ProductVariant, Category, Order, OrderItem, ProductReview
from .filters import ProductFilter
from .serializers import (
    ProductListSerializer, ProductDetailSerializer, ProductCreateSerializer,
    OrderSerializer, CategorySerializer,
)

logger = logging.getLogger("kharandi")


class CategoryListView(generics.ListAPIView):
    queryset           = Category.objects.filter(is_active=True).order_by("order")
    serializer_class   = CategorySerializer
    permission_classes = [AllowAny]


class ProductListCreateView(generics.ListCreateAPIView):
    filter_backends  = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class  = ProductFilter
    search_fields    = ["name", "description", "tags", "vendor__city"]
    ordering_fields  = ["price", "avg_rating", "created_at", "views_count", "reviews_count"]
    ordering         = ["-created_at"]

    def get_permissions(self):
        return [AllowAny()] if self.request.method == "GET" else [IsAuthenticated()]

    def get_queryset(self):
        return Product.objects.filter(
            status=Product.Status.ACTIVE
        ).select_related("vendor", "category").prefetch_related("images", "variants")

    def get_serializer_class(self):
        return ProductCreateSerializer if self.request.method == "POST" else ProductListSerializer

    def create(self, request, *args, **kwargs):
        if request.user.role != "vendor":
            return Response(
                {"success": False, "message": "Seuls les vendeurs peuvent créer des annonces."},
                status=status.HTTP_403_FORBIDDEN
            )
        if not hasattr(request.user, "vendor_profile") or \
           request.user.vendor_profile.kyc_status != "approved":
            return Response(
                {"success": False, "message": "Votre boutique doit être validée (KYC) avant de publier."},
                status=status.HTTP_403_FORBIDDEN
            )
        s = self.get_serializer(data=request.data)
        s.is_valid(raise_exception=True)
        product = s.save()
        return Response(
            {"success": True, "message": "Annonce soumise pour validation.", "data": s.data},
            status=status.HTTP_201_CREATED
        )


class ProductDetailView(generics.RetrieveUpdateDestroyAPIView):

    def get_permissions(self):
        return [AllowAny()] if self.request.method == "GET" else [IsAuthenticated()]

    def get_queryset(self):
        return Product.objects.select_related("vendor", "category").prefetch_related(
            "images", "variants"
        )

    def get_serializer_class(self):
        if self.request.method in ["PUT", "PATCH"]:
            return ProductCreateSerializer
        return ProductDetailSerializer

    def retrieve(self, request, *args, **kwargs):
        product = self.get_object()
        Product.objects.filter(pk=product.pk).update(views_count=F("views_count") + 1)
        data = ProductDetailSerializer(product, context={"request": request}).data
        return Response({"success": True, "data": data})

    def update(self, request, *args, **kwargs):
        product = self.get_object()
        if product.vendor != request.user and not request.user.is_staff:
            return Response({"success": False, "message": "Non autorisé."}, status=403)
        kwargs["partial"] = True
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        product = self.get_object()
        if product.vendor != request.user and not request.user.is_staff:
            return Response({"success": False, "message": "Non autorisé."}, status=403)
        product.status = Product.Status.ARCHIVED
        product.save(update_fields=["status"])
        return Response({"success": True, "message": "Annonce archivée."})


class ProductValidateView(APIView):
    """Admin uniquement — valide ou rejette une annonce et envoie un SMS au vendeur."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not (request.user.is_staff or request.user.role == "admin"):
            return Response({"success": False, "message": "Accès réservé aux admins."}, status=403)
        try:
            product = Product.objects.get(pk=pk)
        except Product.DoesNotExist:
            return Response({"success": False, "message": "Produit introuvable."}, status=404)

        action = request.data.get("action", "approve")
        reason = request.data.get("reason", "")

        if action == "approve":
            product.validate(request.user)
            return Response({"success": True, "message": "Annonce validée et publiée."})
        else:
            product.reject(request.user, reason)
            return Response({"success": True, "message": "Annonce rejetée."})


class MyProductsView(generics.ListAPIView):
    serializer_class   = ProductListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Product.objects.filter(vendor=self.request.user).order_by("-created_at")

    def list(self, request, *args, **kwargs):
        qs = self.get_queryset()
        return Response({"success": True, "data": self.get_serializer(qs, many=True).data})


class ProductReviewCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            product = Product.objects.get(pk=pk, status="active")
        except Product.DoesNotExist:
            return Response({"success": False, "message": "Produit introuvable."}, status=404)

        rating  = request.data.get("rating")
        comment = request.data.get("comment", "")

        if not rating or not (1 <= int(rating) <= 5):
            return Response({"success": False, "message": "Note entre 1 et 5 requise."}, status=400)

        review, created = ProductReview.objects.update_or_create(
            product=product, reviewer=request.user,
            defaults={"rating": int(rating), "comment": comment}
        )
        return Response({
            "success": True,
            "message": "Avis enregistré." if created else "Avis mis à jour.",
        })


class CartCheckoutView(APIView):
    """
    Crée une commande avec déduction de stock atomique (SELECT FOR UPDATE).
    Aucun race condition possible sur le dernier article en stock.
    """
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        items_data = request.data.get("items", [])
        if not items_data:
            return Response({"success": False, "message": "Le panier est vide."}, status=400)

        order_items   = []
        subtotal      = 0
        stock_errors  = []

        for item in items_data:
            variant_id = item.get("variant_id")
            quantity   = max(1, int(item.get("quantity", 1)))

            try:
                variant = ProductVariant.objects.select_for_update().get(
                    pk=variant_id, product__status=Product.Status.ACTIVE
                )
            except ProductVariant.DoesNotExist:
                return Response(
                    {"success": False, "message": f"Variante {variant_id} introuvable."},
                    status=404
                )

            if variant.stock < quantity:
                stock_errors.append(
                    f"'{variant.product.name} — {variant.name}': "
                    f"stock insuffisant ({variant.stock} dispo)."
                )
                continue

            order_items.append((variant, quantity))
            subtotal += float(variant.effective_price) * quantity

        if stock_errors:
            return Response({
                "success": False,
                "message": "Certains articles ne sont plus disponibles.",
                "errors":  stock_errors,
            }, status=status.HTTP_409_CONFLICT)

        rate       = settings.PLATFORM_COMMISSION_RATE
        commission = round(subtotal * rate, 2)
        total      = subtotal

        order = Order.objects.create(
            buyer=request.user,
            subtotal=subtotal,
            commission=commission,
            total=total,
            delivery_address=request.data.get("delivery_address", ""),
            delivery_city=request.data.get("delivery_city", ""),
            delivery_notes=request.data.get("delivery_notes", ""),
        )

        for variant, quantity in order_items:
            OrderItem.objects.create(
                order=order, variant=variant,
                quantity=quantity, price=variant.effective_price,
            )
            ProductVariant.objects.filter(pk=variant.pk).update(
                stock=F("stock") - quantity
            )

        logger.info(f"Commande #{order.order_number} créée — {total} GNF")
        return Response({
            "success": True,
            "message": "Commande créée. Procédez au paiement.",
            "data": {
                "order_id":     order.id,
                "order_number": order.order_number,
                "total":        total,
                "commission":   commission,
            }
        }, status=status.HTTP_201_CREATED)


class OrderListCreateView(generics.ListAPIView):
    serializer_class   = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(buyer=self.request.user).prefetch_related(
            "items__variant__product"
        )

    def list(self, request, *args, **kwargs):
        qs = self.get_queryset()
        return Response({"success": True, "data": self.get_serializer(qs, many=True).data})


class OrderDetailView(generics.RetrieveAPIView):
    serializer_class   = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(buyer=self.request.user)

    def retrieve(self, request, *args, **kwargs):
        return Response({"success": True, "data": self.get_serializer(self.get_object()).data})
