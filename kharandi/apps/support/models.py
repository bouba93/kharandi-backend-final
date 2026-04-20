from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from auditlog.registry import auditlog

User = get_user_model()


class Ticket(models.Model):

    class Priority(models.TextChoices):
        LOW    = "low",    _("Faible")
        MEDIUM = "medium", _("Moyen")
        HIGH   = "high",   _("Élevé")
        URGENT = "urgent", _("Urgent")

    class Status(models.TextChoices):
        OPEN        = "open",        _("Ouvert")
        IN_PROGRESS = "in_progress", _("En cours")
        WAITING     = "waiting",     _("En attente réponse client")
        RESOLVED    = "resolved",    _("Résolu")
        CLOSED      = "closed",      _("Fermé")

    class Category(models.TextChoices):
        PAYMENT   = "payment",   _("Paiement")
        ORDER     = "order",     _("Commande")
        COURSE    = "course",    _("Cours / Répétiteur")
        ACCOUNT   = "account",   _("Compte")
        TECHNICAL = "technical", _("Problème technique")
        OTHER     = "other",     _("Autre")

    user          = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tickets")
    agent         = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL,
                                      related_name="assigned_tickets")
    ticket_number = models.CharField(max_length=20, unique=True)
    subject       = models.CharField(max_length=300)
    description   = models.TextField()
    category      = models.CharField(max_length=20, choices=Category.choices, default=Category.OTHER)
    priority      = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    status        = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN, db_index=True)
    order_number  = models.CharField(max_length=30, blank=True)

    first_response_at  = models.DateTimeField(null=True, blank=True)
    resolved_at        = models.DateTimeField(null=True, blank=True)
    satisfaction_score = models.PositiveSmallIntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = _("Ticket Support")
        verbose_name_plural = _("Tickets Support")
        ordering            = ["-created_at"]
        indexes = [models.Index(fields=["status", "priority"])]

    def __str__(self): return f"#{self.ticket_number} — {self.subject[:50]}"

    def save(self, *args, **kwargs):
        if not self.ticket_number:
            import uuid
            self.ticket_number = f"TKT-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def assign_to(self, agent):
        self.agent  = agent
        self.status = self.Status.IN_PROGRESS
        self.save(update_fields=["agent", "status"])

    def resolve(self):
        self.status      = self.Status.RESOLVED
        self.resolved_at = timezone.now()
        self.save(update_fields=["status", "resolved_at"])
        # SMS au client
        from kharandi.services.sms import send_sms, normalize_phone, sms_ticket_reply
        send_sms(normalize_phone(str(self.user.phone)), sms_ticket_reply(self.ticket_number))


class TicketMessage(models.Model):
    ticket      = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="messages")
    author      = models.ForeignKey(User, on_delete=models.CASCADE)
    content     = models.TextField()
    is_internal = models.BooleanField(default=False)
    attachment  = models.FileField(upload_to="tickets/", blank=True, null=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        # Enregistrer le premier temps de réponse agent
        if is_new and self.author_id != self.ticket.user_id:
            if not self.ticket.first_response_at:
                Ticket.objects.filter(pk=self.ticket_id).update(first_response_at=timezone.now())
            # SMS client si réponse d'un agent (non interne)
            if not self.is_internal:
                from kharandi.services.sms import send_sms, normalize_phone, sms_ticket_reply
                send_sms(
                    normalize_phone(str(self.ticket.user.phone)),
                    sms_ticket_reply(self.ticket.ticket_number)
                )


auditlog.register(Ticket)
