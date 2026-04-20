from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _
from django.utils.text import slugify
from auditlog.registry import auditlog

User = get_user_model()


class Course(models.Model):

    class Level(models.TextChoices):
        PRIMAIRE   = "primaire",   _("Primaire")
        COLLEGE    = "college",    _("Collège")
        LYCEE      = "lycee",      _("Lycée")
        UNIVERSITE = "universite", _("Université")
        AUTRE      = "autre",      _("Autre")

    class Status(models.TextChoices):
        DRAFT   = "draft",   _("Brouillon")
        PENDING = "pending", _("En attente")
        ACTIVE  = "active",  _("Actif")
        PAUSED  = "paused",  _("Suspendu")

    tutor       = models.ForeignKey(User, on_delete=models.CASCADE, related_name="courses",
                                    limit_choices_to={"role": "tutor"})
    title       = models.CharField(max_length=200)
    slug        = models.SlugField(unique=True, blank=True)
    description = models.TextField()
    subject     = models.CharField(max_length=100)
    level       = models.CharField(max_length=20, choices=Level.choices)
    price       = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    is_free     = models.BooleanField(default=False)
    status      = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    tags        = models.CharField(max_length=500, blank=True)
    cover_image = models.ImageField(upload_to="courses/", blank=True, null=True)
    duration_hours = models.PositiveSmallIntegerField(default=0)
    max_students   = models.PositiveSmallIntegerField(null=True, blank=True)

    avg_rating     = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    reviews_count  = models.PositiveIntegerField(default=0)
    students_count = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = _("Cours")
        verbose_name_plural = _("Cours")
        ordering            = ["-created_at"]

    def __str__(self): return f"{self.title} — {self.tutor}"

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title)
            slug = base
            n    = 1
            while Course.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{n}"
                n   += 1
            self.slug = slug
        super().save(*args, **kwargs)


class Enrollment(models.Model):

    class Status(models.TextChoices):
        ACTIVE    = "active",    _("Actif")
        COMPLETED = "completed", _("Terminé")
        DROPPED   = "dropped",   _("Abandonné")

    student    = models.ForeignKey(User, on_delete=models.CASCADE, related_name="enrollments")
    course     = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="enrollments")
    status     = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    progress   = models.PositiveSmallIntegerField(default=0, validators=[MaxValueValidator(100)])
    enrolled_at  = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    last_activity = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together     = [["student", "course"]]
        verbose_name        = _("Inscription")
        verbose_name_plural = _("Inscriptions")

    def __str__(self): return f"{self.student} → {self.course.title}"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        if is_new:
            Course.objects.filter(pk=self.course_id).update(
                students_count=models.F("students_count") + 1
            )
            # SMS répétiteur (synchrone NimbaSMS)
            from kharandi.services.sms import send_sms, normalize_phone, sms_new_student
            send_sms(
                normalize_phone(str(self.course.tutor.phone)),
                sms_new_student(self.student.get_full_name(), self.course.title)
            )
            # Mettre à jour total_students du profil répétiteur
            from kharandi.apps.accounts.models import TutorProfile
            TutorProfile.objects.filter(user=self.course.tutor).update(
                total_students=models.F("total_students") + 1
            )


class Grade(models.Model):
    student      = models.ForeignKey(User, on_delete=models.CASCADE, related_name="grades")
    course       = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="grades")
    score        = models.DecimalField(max_digits=5, decimal_places=2)
    max_score    = models.DecimalField(max_digits=5, decimal_places=2, default=20)
    grade_letter = models.CharField(max_length=5, blank=True)
    notes        = models.TextField(blank=True)
    graded_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together     = [["student", "course"]]
        verbose_name        = _("Note")
        verbose_name_plural = _("Notes")

    def __str__(self): return f"{self.student} — {self.course.subject}: {self.score}/{self.max_score}"

    def save(self, *args, **kwargs):
        # Auto-calculer la mention
        if not self.grade_letter and self.max_score:
            pct = float(self.score) / float(self.max_score) * 20
            if pct >= 16:   self.grade_letter = "TB"
            elif pct >= 14: self.grade_letter = "B"
            elif pct >= 12: self.grade_letter = "AB"
            elif pct >= 10: self.grade_letter = "P"
            else:           self.grade_letter = "F"
        super().save(*args, **kwargs)


auditlog.register(Course)
auditlog.register(Enrollment)
