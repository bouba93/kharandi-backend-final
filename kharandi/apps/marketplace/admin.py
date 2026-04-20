from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline
from .models import Category, Product, ProductVariant, ProductImage, Order, OrderItem


class ProductVariantInline(TabularInline):
    model  = ProductVariant
    extra  = 1
    fields = ["name", "price_override", "stock", "sku"]

class ProductImageInline(TabularInline):
    model  = ProductImage
    extra  = 1
    fields = ["image", "alt_text", "is_main", "order"]

class OrderItemInline(TabularInline):
    model       = OrderItem
    extra       = 0
    readonly_fields = ["variant", "quantity", "price"]
    can_delete  = False

@admin.register(Category)
class CategoryAdmin(ModelAdmin):
    list_display = ["name", "slug", "parent", "is_active", "order"]
    list_filter  = ["is_active"]
    search_fields = ["name"]
    prepopulated_fields = {"slug": ("name",)}

@admin.register(Product)
class ProductAdmin(ModelAdmin):
    list_display  = ["name", "vendor", "category", "price", "status", "avg_rating", "views_count", "created_at"]
    list_filter   = ["status", "category"]
    search_fields = ["name", "vendor__phone", "vendor__first_name"]
    readonly_fields = ["avg_rating", "reviews_count", "views_count", "created_at", "updated_at", "published_at"]
    inlines       = [ProductVariantInline, ProductImageInline]
    actions       = ["validate_products", "reject_products"]

    @admin.action(description="✅ Valider et publier")
    def validate_products(self, request, queryset):
        for p in queryset.filter(status="pending"):
            p.validate(request.user)
        self.message_user(request, f"{queryset.count()} produit(s) validé(s).")

    @admin.action(description="❌ Rejeter")
    def reject_products(self, request, queryset):
        for p in queryset.filter(status="pending"):
            p.reject(request.user, "Non conforme aux règles Kharandi")
        self.message_user(request, f"{queryset.count()} produit(s) rejeté(s).")

@admin.register(Order)
class OrderAdmin(ModelAdmin):
    list_display  = ["order_number", "buyer", "status", "total", "commission", "created_at", "paid_at"]
    list_filter   = ["status", "created_at"]
    search_fields = ["order_number", "buyer__phone", "buyer__first_name"]
    readonly_fields = ["order_number", "buyer", "subtotal", "commission", "total", "lengopay_id", "paid_at", "created_at"]
    inlines       = [OrderItemInline]
    actions       = ["mark_shipped", "mark_delivered"]

    @admin.action(description="📦 Marquer comme expédiées")
    def mark_shipped(self, request, queryset):
        for o in queryset.filter(status="paid"):
            o.mark_as_shipped()
        self.message_user(request, "Commandes marquées expédiées + SMS envoyés.")

    @admin.action(description="✅ Marquer comme livrées")
    def mark_delivered(self, request, queryset):
        for o in queryset.filter(status="shipped"):
            o.mark_as_delivered()
        self.message_user(request, "Commandes marquées livrées + SMS envoyés.")
