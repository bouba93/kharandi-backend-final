from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from auditlog.registry import auditlog

User = get_user_model()


class Transaction(models.Model):

    class Type(models.TextChoices):
        PRODUCT  = "product",  _("Achat produit")
        COURSE   = "course",   _("Achat cours")
        SUB      = "sub",      _("Abonnement")
        REFUND   = "refund",   _("Remboursement")

    class Status(models.TextChoices):
        PENDING  = "pending",  _("En attente")
        SUCCESS  = "success",  _("Succès")
        FAILED   = "failed",   _("Échoué")
        REFUNDED = "refunded", _("Remboursé")

    payer     = models.ForeignKey(User, on_delete=models.PROTECT,
                                  related_name="payments_made")
    recipient = models.ForeignKey(User, null=True, blank=True,
                                  on_delete=models.SET_NULL,
                                  related_name="payments_received")

    amount           = models.DecimalField(max_digits=15, decimal_places=2)
    commission_rate  = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    commission_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    net_amount       = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    lengopay_id      = models.CharField(max_length=100, unique=True, null=True, blank=True, db_index=True)
    lengopay_payload = models.JSONField(null=True, blank=True)

    transaction_type = models.CharField(max_length=20, choices=Type.choices, default=Type.PRODUCT)
    order  = models.OneToOneField("marketplace.Order", null=True, blank=True,
                                  on_delete=models.SET_NULL, related_name="transaction")
    course = models.ForeignKey("courses.Course", null=True, blank=True,
                               on_delete=models.SET_NULL, related_name="transactions")

    status         = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    failure_reason = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = _("Transaction")
        verbose_name_plural = _("Transactions")
        ordering            = ["-created_at"]
        indexes = [
            models.Index(fields=["payer", "status"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.lengopay_id or 'PENDING'} — {self.amount} GNF ({self.status})"


class Commission(models.Model):
    transaction       = models.OneToOneField(Transaction, on_delete=models.CASCADE,
                                             related_name="commission_record")
    vendor            = models.ForeignKey(User, on_delete=models.PROTECT,
                                          related_name="commissions_paid")
    rate              = models.DecimalField(max_digits=5, decimal_places=4)
    gross_amount      = models.DecimalField(max_digits=15, decimal_places=2)
    commission_amount = models.DecimalField(max_digits=15, decimal_places=2)
    net_amount        = models.DecimalField(max_digits=15, decimal_places=2)
    is_paid_to_vendor = models.BooleanField(default=False)
    paid_at           = models.DateTimeField(null=True, blank=True)
    created_at        = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = _("Commission")
        verbose_name_plural = _("Commissions")
        ordering            = ["-created_at"]


class Invoice(models.Model):
    transaction    = models.OneToOneField(Transaction, on_delete=models.CASCADE,
                                          related_name="invoice")
    invoice_number = models.CharField(max_length=30, unique=True)
    pdf_file       = models.FileField(upload_to="invoices/", null=True, blank=True)
    issued_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = _("Facture")
        verbose_name_plural = _("Factures")

    def __str__(self): return self.invoice_number


auditlog.register(Transaction)
auditlog.register(Commission)
