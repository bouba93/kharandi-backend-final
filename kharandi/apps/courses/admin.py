from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline
from .models import Course, Enrollment, Grade

class EnrollmentInline(TabularInline):
    model       = Enrollment
    extra       = 0
    readonly_fields = ["student","progress","status","enrolled_at"]
    can_delete  = False

@admin.register(Course)
class CourseAdmin(ModelAdmin):
    list_display  = ["title","tutor","subject","level","price","status","students_count","avg_rating"]
    list_filter   = ["status","level","subject"]
    search_fields = ["title","tutor__phone","tutor__first_name","subject"]
    readonly_fields = ["avg_rating","reviews_count","students_count","created_at","updated_at"]
    inlines       = [EnrollmentInline]
    actions       = ["approve","pause"]

    @admin.action(description="✅ Approuver les cours")
    def approve(self, request, queryset):
        queryset.filter(status="pending").update(status="active")
        self.message_user(request, f"Cours approuvés.")

    @admin.action(description="⏸ Suspendre les cours")
    def pause(self, request, queryset):
        queryset.update(status="paused")

@admin.register(Enrollment)
class EnrollmentAdmin(ModelAdmin):
    list_display  = ["student","course","status","progress","enrolled_at"]
    list_filter   = ["status"]
    search_fields = ["student__phone","course__title"]

@admin.register(Grade)
class GradeAdmin(ModelAdmin):
    list_display  = ["student","course","score","max_score","grade_letter","graded_at"]
    search_fields = ["student__phone","course__title"]
