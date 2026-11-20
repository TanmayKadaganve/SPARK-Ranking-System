from django.contrib import admin
from django.utils.html import format_html, format_html_join

from .models import CATEGORY_DEFINITIONS, Member, RankingPeriod, ScoreCategory, ScoreEntry
from .number_fields import format_points
from .services import build_rankings


admin.site.site_header = "SPARK Club Administration"
admin.site.site_title = "SPARK Admin"
admin.site.index_title = "Members and score management"


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ("full_name", "usn", "semester", "branch", "team_name", "current_total", "is_active")
    list_filter = ("is_active", "semester", "branch", "team_name")
    search_fields = ("full_name", "usn")
    ordering = ("full_name", "usn")
    list_per_page = 50
    readonly_fields = ("created_at", "current_rank", "score_breakdown")
    fieldsets = (
        ("Member", {"fields": ("full_name", "usn", "profile_image")} ),
        ("Club details", {"fields": ("semester", "branch", "team_name", "date_joined", "is_active")} ),
        ("Current ranking", {"fields": ("current_rank", "score_breakdown")} ),
        ("Record", {"fields": ("created_at",), "classes": ("collapse",)}),
    )
    actions = ("deactivate_members", "activate_members")

    def changelist_view(self, request, extra_context=None):
        self._ranking_cache = {row["member"].pk: row for row in build_rankings(include_inactive=True)}
        return super().changelist_view(request, extra_context)

    def _row(self, obj):
        cache = getattr(self, "_ranking_cache", None)
        if cache is None:
            cache = {row["member"].pk: row for row in build_rankings(include_inactive=True)}
            self._ranking_cache = cache
        return cache.get(obj.pk, {"rank": "—", "scores": {}, "total": 0})

    @admin.display(description="Total points", ordering=None)
    def current_total(self, obj):
        return format_points(self._row(obj)["total"])

    @admin.display(description="Current overall rank")
    def current_rank(self, obj):
        row = self._row(obj)
        return f"#{row['rank']}" if row["rank"] != "—" else "—"

    @admin.display(description="Category score breakdown")
    def score_breakdown(self, obj):
        row = self._row(obj)
        labels = [(code, label) for code, label, _ in CATEGORY_DEFINITIONS]
        rows = format_html_join(
            "",
            "<tr><th scope='row'>{}</th><td>{}</td></tr>",
            ((label, format_points(row["scores"].get(code, 0))) for code, label in labels),
        )
        rows += format_html("<tr class='spark-total'><th scope='row'>TOTAL</th><td>{}</td></tr>", format_points(row["total"]))
        return format_html("<table class='spark-breakdown'>{}</table>", rows)

    @admin.action(description="Deactivate selected members")
    def deactivate_members(self, request, queryset):
        queryset.update(is_active=False)

    @admin.action(description="Activate selected members")
    def activate_members(self, request, queryset):
        queryset.update(is_active=True)


@admin.register(ScoreCategory)
class ScoreCategoryAdmin(admin.ModelAdmin):
    list_display = ("category_name", "code", "is_active", "sort_order")
    list_filter = ("is_active",)
    search_fields = ("category_name", "description", "code")
    ordering = ("sort_order",)

    def has_add_permission(self, request):
        # The six canonical score categories are created by the data migration.
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ScoreEntry)
class ScoreEntryAdmin(admin.ModelAdmin):
    list_display = ("date_awarded", "created_at", "member", "category", "formatted_points", "reason_preview", "awarded_by")
    list_filter = ("category", ("date_awarded", admin.DateFieldListFilter), "member__semester", "member__team_name")
    search_fields = ("member__full_name", "member__usn", "reason", "awarded_by__username", "awarded_by__first_name", "awarded_by__last_name")
    date_hierarchy = "date_awarded"
    ordering = ("-date_awarded", "-created_at")
    list_select_related = ("member", "category", "awarded_by")
    list_per_page = 50
    autocomplete_fields = ("member",)
    fields = ("member", "category", "points", "reason", "date_awarded", "awarded_by", "ranking_period", "created_at")

    def get_form(self, request, obj=None, **kwargs):
        from .forms import ScoreEntryAdminForm

        kwargs["form"] = ScoreEntryAdminForm
        return super().get_form(request, obj, **kwargs)

    def get_readonly_fields(self, request, obj=None):
        if obj:
            # Award records are immutable; corrections are new transactions.
            return tuple(field.name for field in self.model._meta.fields)
        return ("awarded_by", "ranking_period", "created_at")

    def save_model(self, request, obj, form, change):
        if change:
            return
        obj.awarded_by = request.user
        super().save_model(request, obj, form, change)

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="Points")
    def formatted_points(self, obj):
        return format_points(obj.points)

    @admin.display(description="Reason")
    def reason_preview(self, obj):
        return obj.reason if len(obj.reason) <= 100 else obj.reason[:97] + "…"


@admin.register(RankingPeriod)
class RankingPeriodAdmin(admin.ModelAdmin):
    list_display = ("name", "start_date", "end_date", "score_count", "is_active")
    list_filter = ("is_active",)
    ordering = ("-start_date",)
    readonly_fields = ("name", "start_date", "end_date", "score_count", "is_active")

    @admin.display(description="Score entries")
    def score_count(self, obj):
        return obj.score_entries.count()

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
