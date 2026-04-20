from django.contrib import admin
from django.utils import timezone
from unfold.admin import ModelAdmin
from .models import Transaction, Commission, Invoice

@admin.register(Transaction)
class TransactionAdmin(ModelAdmin):
    list_display  = ["lengopay_id", "payer", "amount", "commission_amount", "net_amount", "status", "created_at"]
    list_filter   = ["status", "transaction_type", "created_at"]
    search_fields = ["lengopay_id", "payer__phone", "payer__first_name"]
    readonly_fields = ["lengopay_id", "payer", "amount", "commission_rate", "commission_amount",
                       "net_amount", "lengopay_payload", "created_at", "updated_at"]

@admin.register(Commission)
class CommissionAdmin(ModelAdmin):
    list_display  = ["transaction", "vendor", "gross_amount", "commission_amount", "net_amount", "is_paid_to_vendor"]
    list_filter   = ["is_paid_to_vendor"]
    search_fields = ["vendor__phone"]
    actions       = ["mark_paid"]

    @admin.action(description="💰 Marquer comme versées aux vendeurs")
    def mark_paid(self, request, queryset):
        queryset.filter(is_paid_to_vendor=False).update(is_paid_to_vendor=True, paid_at=timezone.now())
        self.message_user(request, "Commissions marquées versées.")

@admin.register(Invoice)
class InvoiceAdmin(ModelAdmin):
    list_display  = ["invoice_number", "transaction", "issued_at"]
    search_fields = ["invoice_number"]
    readonly_fields = ["invoice_number", "transaction", "issued_at"]
