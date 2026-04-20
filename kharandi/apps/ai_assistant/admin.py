from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import AIConversation, AIMessage, AIUsageLog

class AIMessageInline(admin.TabularInline):
    model       = AIMessage
    extra       = 0
    readonly_fields = ["role","content","tokens_used","was_cached","created_at"]
    can_delete  = False

@admin.register(AIConversation)
class AIConversationAdmin(ModelAdmin):
    list_display  = ["id","user","title","subject","updated_at","is_active"]
    list_filter   = ["subject","is_active"]
    search_fields = ["user__phone","title"]
    readonly_fields = ["user","created_at","updated_at"]
    inlines       = [AIMessageInline]

@admin.register(AIUsageLog)
class AIUsageLogAdmin(ModelAdmin):
    list_display  = ["user","date","questions","tokens"]
    list_filter   = ["date"]
    search_fields = ["user__phone"]
    readonly_fields = ["user","date","questions","tokens"]
