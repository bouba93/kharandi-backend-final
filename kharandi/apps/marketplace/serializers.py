from rest_framework import serializers
from .models import Product, ProductVariant, ProductImage, Category, Order, OrderItem


class CategorySerializer(serializers.ModelSerializer):
    children_count = serializers.SerializerMethodField()
    class Meta:
        model  = Category
        fields = ["id", "name", "slug", "icon", "parent", "children_count"]
    def get_children_count(self, obj): return obj.children.filter(is_active=True).count()


class ProductVariantSerializer(serializers.ModelSerializer):
    effective_price = serializers.ReadOnlyField()
    class Meta:
        model  = ProductVariant
        fields = ["id", "name", "effective_price", "stock", "sku"]


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ProductImage
        fields = ["id", "image", "alt_text", "is_main"]


class ProductListSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True, default="")
    vendor_shop   = serializers.SerializerMethodField()
    main_image    = serializers.SerializerMethodField()
    is_available  = serializers.ReadOnlyField()

    class Meta:
        model  = Product
        fields = ["id", "name", "slug", "price", "category_name", "vendor_shop",
                  "avg_rating", "reviews_count", "views_count", "is_available", "main_image"]

    def get_vendor_shop(self, obj):
        try: return obj.vendor.vendor_profile.shop_name
        except Exception: return ""

    def get_main_image(self, obj):
        img = obj.images.filter(is_main=True).first() or obj.images.first()
        if img and img.image:
            r = self.context.get("request")
            return r.build_absolute_uri(img.image.url) if r else img.image.url
        return None


class ProductDetailSerializer(ProductListSerializer):
    variants = ProductVariantSerializer(many=True, read_only=True)
    images   = ProductImageSerializer(many=True, read_only=True)

    class Meta(ProductListSerializer.Meta):
        fields = ProductListSerializer.Meta.fields + [
            "description", "tags", "variants", "images",
            "created_at", "meta_title", "meta_description",
        ]


class ProductCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Product
        fields = ["name", "description", "price", "category", "tags",
                  "meta_title", "meta_description"]
    def create(self, validated_data):
        validated_data["vendor"] = self.context["request"].user
        return super().create(validated_data)


class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="variant.product.name", read_only=True)
    variant_name = serializers.CharField(source="variant.name", read_only=True)
    subtotal     = serializers.ReadOnlyField()
    class Meta:
        model  = OrderItem
        fields = ["id", "product_name", "variant_name", "quantity", "price", "subtotal"]


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    class Meta:
        model  = Order
        fields = ["id", "order_number", "status", "subtotal", "commission",
                  "total", "delivery_address", "delivery_city", "items", "created_at", "paid_at"]
        read_only_fields = ["order_number", "status", "subtotal", "commission", "total", "paid_at"]
