from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline
from .models import Ticket, TicketMessage

class TicketMessageInline(TabularInline):
    model       = TicketMessage
    extra       = 1
    fields      = ["author","content","is_internal"]
    readonly_fields = ["created_at"]

@admin.register(Ticket)
class TicketAdmin(ModelAdmin):
    list_display  = ["ticket_number","user","subject","category","priority","status","agent","created_at"]
    list_filter   = ["status","priority","category"]
    search_fields = ["ticket_number","user__phone","subject"]
    readonly_fields = ["ticket_number","created_at","updated_at","first_response_at","resolved_at"]
    inlines       = [TicketMessageInline]
    actions       = ["resolve_tickets","assign_to_me"]

    @admin.action(description="✅ Résoudre les tickets sélectionnés")
    def resolve_tickets(self, request, queryset):
        for t in queryset: t.resolve()
        self.message_user(request, f"{queryset.count()} ticket(s) résolu(s) + SMS envoyés.")

    @admin.action(description="🙋 M'assigner ces tickets")
    def assign_to_me(self, request, queryset):
        for t in queryset.filter(status="open"): t.assign_to(request.user)
        self.message_user(request, f"{queryset.count()} ticket(s) assigné(s).")
