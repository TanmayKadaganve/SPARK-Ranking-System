from calendar import monthrange
from datetime import date

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from .number_fields import UnlimitedIntegerField


CATEGORY_DEFINITIONS = (
    ("teaching", "Teaching / SkillXchange", "Teaching, mentoring, workshops, and knowledge sharing."),
    ("projects", "Project Development", "Project work, functional modules, prototypes, and demonstrations."),
    ("attendance", "Attendance", "Meetings, workshops, technical sessions, and assigned activities."),
    ("discipline", "Discipline", "Responsibility, punctuality, conduct, cooperation, and rule violations."),
    ("events", "Event Winning", "Competition, hackathon, exhibition, and other event achievements."),
    ("skills", "Skill Points", "Learning, coding practice, certifications, and demonstrated technical growth."),
)


class Member(models.Model):
    full_name = models.CharField(max_length=160, db_index=True)
    usn = models.CharField("USN", max_length=32, unique=True, db_index=True)
    semester = models.PositiveSmallIntegerField(db_index=True)
    branch = models.CharField(max_length=100, blank=True)
    team_name = models.CharField(max_length=100, blank=True, db_index=True)
    profile_image = models.ImageField(upload_to="members/", blank=True)
    date_joined = models.DateField(default=timezone.localdate)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("full_name", "usn")
        indexes = [models.Index(fields=("is_active", "semester", "team_name"))]

    def __str__(self):
        return f"{self.full_name} ({self.usn})"


class ScoreCategory(models.Model):
    code = models.SlugField(max_length=32, unique=True)
    category_name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("sort_order", "category_name")
        verbose_name_plural = "score categories"

    def __str__(self):
        return self.category_name


class RankingPeriod(models.Model):
    name = models.CharField(max_length=80)
    start_date = models.DateField(unique=True)
    end_date = models.DateField()
    is_active = models.BooleanField(default=False)

    class Meta:
        ordering = ("-start_date",)
        constraints = [
            models.CheckConstraint(condition=Q(end_date__gte=models.F("start_date")), name="ranking_period_valid_dates"),
        ]

    def __str__(self):
        return self.name

    @classmethod
    def for_date(cls, awarded_date):
        if not isinstance(awarded_date, date):
            raise ValueError("A score award date is required to determine its ranking period.")
        start = date(awarded_date.year, awarded_date.month, 1)
        end = date(awarded_date.year, awarded_date.month, monthrange(awarded_date.year, awarded_date.month)[1])
        now = timezone.localdate()
        active = (start.year, start.month) == (now.year, now.month)
        period, _ = cls.objects.get_or_create(
            start_date=start,
            defaults={"name": start.strftime("%B %Y"), "end_date": end, "is_active": active},
        )
        if period.end_date != end:
            period.end_date = end
            period.save(update_fields=("end_date",))
        if active:
            cls.objects.filter(is_active=True).exclude(pk=period.pk).update(is_active=False)
            if not period.is_active:
                period.is_active = True
                period.save(update_fields=("is_active",))
        return period


class ScoreEntry(models.Model):
    member = models.ForeignKey(Member, on_delete=models.PROTECT, related_name="score_entries")
    category = models.ForeignKey(ScoreCategory, on_delete=models.PROTECT, related_name="score_entries")
    points = UnlimitedIntegerField(help_text="Any whole number; negative amounts are allowed for deductions.")
    reason = models.TextField("Reason / description")
    awarded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="spark_score_entries",
    )
    date_awarded = models.DateField(default=timezone.localdate, db_index=True)
    ranking_period = models.ForeignKey(
        RankingPeriod,
        on_delete=models.PROTECT,
        related_name="score_entries",
        editable=False,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-date_awarded", "-created_at", "-pk")
        indexes = [models.Index(fields=("member", "category", "date_awarded"))]
        constraints = [
            models.CheckConstraint(condition=~Q(reason=""), name="score_entry_reason_not_empty"),
        ]

    def __str__(self):
        return f"{self.member.full_name}: {self.points} {self.category.category_name}"

    def clean(self):
        super().clean()
        if self.reason is not None and not self.reason.strip():
            raise ValidationError({"reason": "Explain why these points are being awarded or deducted."})
        if self.date_awarded:
            self.ranking_period = RankingPeriod.for_date(self.date_awarded)

    def save(self, *args, **kwargs):
        if not self.reason or not self.reason.strip():
            raise ValidationError({"reason": "Explain why these points are being awarded or deducted."})
        self.ranking_period = RankingPeriod.for_date(self.date_awarded)
        if kwargs.get("update_fields") is not None:
            kwargs["update_fields"] = tuple(set(kwargs["update_fields"]) | {"ranking_period"})
        super().save(*args, **kwargs)
