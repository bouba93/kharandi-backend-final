from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

User = get_user_model()


class AIConversation(models.Model):
    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name="ai_conversations")
    title      = models.CharField(max_length=200, blank=True)
    subject    = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active  = models.BooleanField(default=True)

    class Meta:
        verbose_name        = _("Conversation IA")
        verbose_name_plural = _("Conversations IA")
        ordering            = ["-updated_at"]

    def __str__(self):
        return f"Conv {self.id} — {self.user}"


class AIMessage(models.Model):

    class Role(models.TextChoices):
        USER      = "user",      _("Élève")
        ASSISTANT = "assistant", _("Karamö")

    conversation = models.ForeignKey(AIConversation, on_delete=models.CASCADE, related_name="messages")
    role         = models.CharField(max_length=20, choices=Role.choices)
    content      = models.TextField()
    tokens_used  = models.PositiveIntegerField(default=0)
    was_cached   = models.BooleanField(default=False)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class AIUsageLog(models.Model):
    """Suivi de la consommation IA par utilisateur par jour."""
    user      = models.ForeignKey(User, on_delete=models.CASCADE, related_name="ai_usage")
    date      = models.DateField(default=timezone.now)
    questions = models.PositiveIntegerField(default=0)
    tokens    = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together     = [["user", "date"]]
        verbose_name        = _("Consommation IA")
        verbose_name_plural = _("Consommations IA")

    def __str__(self):
        return f"{self.user} — {self.date} — {self.questions} questions"
