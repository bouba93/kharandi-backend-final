from django.db import models, transaction
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _
from django.utils.text import slugify
from auditlog.registry import auditlog

User = get_user_model()


class Category(models.Model):
    name      = models.CharField(max_length=100)
    slug      = models.SlugField(unique=True, blank=True)
    icon      = models.CharField(max_length=50, blank=True)
    parent    = models.ForeignKey("self", null=True, blank=True,
                                  on_delete=models.SET_NULL, related_name="children")
    is_active = models.BooleanField(default=True)
    order     = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name        = _("Catégorie")
        verbose_name_plural = _("Catégories")
        ordering            = ["order", "name"]

    def __str__(self): return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Product(models.Model):

    class Status(models.TextChoices):
        DRAFT    = "draft",    _("Brouillon")
        PENDING  = "pending",  _("En attente de validation")
        ACTIVE   = "active",   _("Actif")
        REJECTED = "rejected", _("Rejeté")
        ARCHIVED = "archived", _("Archivé")

    vendor    = models.ForeignKey(User, on_delete=models.CASCADE, related_name="products",
                                  limit_choices_to={"role": "vendor"})
    category  = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name="products")
    name      = models.CharField(max_length=200)
    slug      = models.SlugField(max_length=250, unique=True, blank=True)
    description = models.TextField()
    price     = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    status    = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    tags      = models.CharField(max_length=500, blank=True)

    # SEO
    meta_title       = models.CharField(max_length=200, blank=True)
    meta_description = models.CharField(max_length=300, blank=True)

    # Stats
    views_count   = models.PositiveIntegerField(default=0)
    avg_rating    = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    reviews_count = models.PositiveIntegerField(default=0)

    # Validation admin
    validated_by     = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL,
                                         related_name="validated_products")
    rejection_reason = models.TextField(blank=True)

    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name        = _("Produit")
        verbose_name_plural = _("Produits")
        ordering            = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "category"]),
            models.Index(fields=["vendor", "status"]),
        ]

    def __str__(self): return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)
            slug = base
            n = 1
            while Product.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{n}"
                n += 1
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def is_available(self):
        return self.status == self.Status.ACTIVE and self.variants.filter(stock__gt=0).exists()

    def validate(self, admin_user):
        from django.utils import timezone
        from kharandi.services.sms import send_sms, normalize_phone, sms_annonce_validated
        self.status       = self.Status.ACTIVE
        self.validated_by = admin_user
        self.published_at = timezone.now()
        self.save(update_fields=["status", "validated_by", "published_at"])
        send_sms(normalize_phone(str(self.vendor.phone)), sms_annonce_validated(self.name))

    def reject(self, admin_user, reason: str = ""):
        from kharandi.services.sms import send_sms, normalize_phone, sms_annonce_rejected
        self.status          = self.Status.REJECTED
        self.rejection_reason = reason
        self.validated_by    = admin_user
        self.save(update_fields=["status", "rejection_reason", "validated_by"])
        send_sms(normalize_phone(str(self.vendor.phone)), sms_annonce_rejected(self.name, reason))


class ProductImage(models.Model):
    product  = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    image    = models.ImageField(upload_to="products/")
    alt_text = models.CharField(max_length=200, blank=True)
    is_main  = models.BooleanField(default=False)
    order    = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order"]


class ProductVariant(models.Model):
    product        = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    name           = models.CharField(max_length=100, help_text="Ex: Rouge M, Taille 38")
    price_override = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    stock          = models.PositiveIntegerField(default=0)
    sku            = models.CharField(max_length=100, blank=True, null=True, unique=True)

    class Meta:
        verbose_name        = _("Variante")
        verbose_name_plural = _("Variantes")

    def __str__(self): return f"{self.product.name} — {self.name}"

    @property
    def effective_price(self):
        return self.price_override or self.product.price

    @transaction.atomic
    def deduct_stock(self, qty: int) -> bool:
        """SELECT FOR UPDATE pour éviter les race conditions."""
        variant = ProductVariant.objects.select_for_update().get(pk=self.pk)
        if variant.stock < qty:
            return False
        ProductVariant.objects.filter(pk=self.pk).update(stock=models.F("stock") - qty)
        self.stock = variant.stock - qty
        return True

    @transaction.atomic
    def restore_stock(self, qty: int):
        ProductVariant.objects.filter(pk=self.pk).update(stock=models.F("stock") + qty)


class Order(models.Model):

    class Status(models.TextChoices):
        PENDING    = "pending",    _("En attente de paiement")
        PAID       = "paid",       _("Payé")
        PROCESSING = "processing", _("En préparation")
        SHIPPED    = "shipped",    _("Expédié")
        DELIVERED  = "delivered",  _("Livré")
        CANCELLED  = "cancelled",  _("Annulé")
        REFUNDED   = "refunded",   _("Remboursé")

    buyer        = models.ForeignKey(User, on_delete=models.PROTECT, related_name="orders")
    order_number = models.CharField(max_length=20, unique=True, db_index=True)
    status       = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)

    subtotal   = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    commission = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total      = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    delivery_address = models.TextField(blank=True)
    delivery_city    = models.CharField(max_length=100, blank=True)
    delivery_notes   = models.TextField(blank=True)

    lengopay_id = models.CharField(max_length=100, blank=True, db_index=True)
    paid_at     = models.DateTimeField(null=True, blank=True)

    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name        = _("Commande")
        verbose_name_plural = _("Commandes")
        ordering            = ["-created_at"]
        indexes = [
            models.Index(fields=["buyer", "status"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self): return f"#{self.order_number}"

    def save(self, *args, **kwargs):
        if not self.order_number:
            import uuid
            self.order_number = f"KH{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def mark_as_paid(self, lengopay_id: str):
        from django.utils import timezone
        from kharandi.services.sms import send_sms, normalize_phone, sms_order_confirmation
        self.status      = self.Status.PAID
        self.lengopay_id = lengopay_id
        self.paid_at     = timezone.now()
        self.save(update_fields=["status", "lengopay_id", "paid_at"])
        # SMS acheteur
        send_sms(
            normalize_phone(str(self.buyer.phone)),
            sms_order_confirmation(self.order_number, int(self.total))
        )
        # Points fidélité : 1 point / 10 000 GNF
        pts = int(self.total / 10000)
        if pts > 0:
            self.buyer.credit_points(pts, reason=f"Commande #{self.order_number}")

    def mark_as_shipped(self):
        from kharandi.services.sms import send_sms, normalize_phone, sms_order_shipped
        self.status = self.Status.SHIPPED
        self.save(update_fields=["status"])
        send_sms(normalize_phone(str(self.buyer.phone)), sms_order_shipped(self.order_number))

    def mark_as_delivered(self):
        from kharandi.services.sms import send_sms, normalize_phone, sms_order_delivered
        self.status = self.Status.DELIVERED
        self.save(update_fields=["status"])
        send_sms(normalize_phone(str(self.buyer.phone)), sms_order_delivered(self.order_number))


class OrderItem(models.Model):
    order    = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    variant  = models.ForeignKey(ProductVariant, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=1)
    price    = models.DecimalField(max_digits=12, decimal_places=2)

    @property
    def subtotal(self): return self.price * self.quantity

    class Meta:
        verbose_name        = _("Ligne commande")
        verbose_name_plural = _("Lignes commande")


class ProductReview(models.Model):
    product    = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="reviews")
    reviewer   = models.ForeignKey(User, on_delete=models.CASCADE)
    rating     = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment    = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [["product", "reviewer"]]
        verbose_name    = _("Avis")

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        from django.db.models import Avg, Count
        agg = ProductReview.objects.filter(product=self.product).aggregate(
            avg=Avg("rating"), cnt=Count("id")
        )
        Product.objects.filter(pk=self.product_id).update(
            avg_rating=agg["avg"] or 0, reviews_count=agg["cnt"]
        )
        # SMS vendeur pour le premier avis de la journée
        from kharandi.services.sms import send_sms, normalize_phone, sms_new_review
        if self._state.adding:
            send_sms(
                normalize_phone(str(self.product.vendor.phone)),
                sms_new_review(self.rating, self.product.name)
            )


auditlog.register(Product)
auditlog.register(Order)
