from datetime import date

from django.conf import settings
from django.core.paginator import Paginator
from django.shortcuts import render
from django.utils import timezone

from .models import Member, RankingPeriod
from .services import build_rankings, validate_month


def leaderboard(request):
    mode = request.GET.get("mode", "overall")
    if mode not in {"overall", "monthly"}:
        mode = "overall"

    current_month = timezone.localdate().strftime("%Y-%m")
    month = request.GET.get("month", current_month)
    if not validate_month(month):
        month = current_month

    ranked = build_rankings(mode=mode, month=month)
    search = request.GET.get("q", "").strip()
    semester = request.GET.get("semester", "").strip()
    team = request.GET.get("team", "").strip()

    # Rankings are computed for the full active roster first, so search and
    # filters never change a member's actual position.
    if search:
        needle = search.casefold()
        ranked = [
            row for row in ranked
            if needle in row["member"].full_name.casefold()
            or (settings.PUBLIC_SHOW_USN and needle in row["member"].usn.casefold())
        ]
    if semester:
        ranked = [row for row in ranked if str(row["member"].semester) == semester]
    if team:
        ranked = [row for row in ranked if row["member"].team_name == team]

    paginator = Paginator(ranked, 50)
    page_obj = paginator.get_page(request.GET.get("page"))

    month_values = {current_month}
    first_joined = Member.objects.order_by("date_joined").values_list("date_joined", flat=True).first()
    if first_joined:
        cursor = date(first_joined.year, first_joined.month, 1)
        current_today = timezone.localdate()
        current_start = date(current_today.year, current_today.month, 1)
        while cursor <= current_start:
            month_values.add(cursor.strftime("%Y-%m"))
            cursor = date(cursor.year + (cursor.month == 12), 1 if cursor.month == 12 else cursor.month + 1, 1)
    month_values.update(period.start_date.strftime("%Y-%m") for period in RankingPeriod.objects.all())
    months = []
    for value in sorted(month_values, reverse=True):
        year, month_number = (int(part) for part in value.split("-"))
        month_date = date(year, month_number, 1)
        months.append((value, month_date.strftime("%B %Y")))

    query = request.GET.copy()
    query.pop("page", None)
    context = {
        "page_obj": page_obj,
        "mode": mode,
        "month": month,
        "months": months,
        "search": search,
        "selected_semester": semester,
        "selected_team": team,
        "semesters": Member.objects.filter(is_active=True).values_list("semester", flat=True).distinct().order_by("semester"),
        "teams": Member.objects.filter(is_active=True).exclude(team_name="").values_list("team_name", flat=True).distinct().order_by("team_name"),
        "query_string": query.urlencode(),
        "show_usn": settings.PUBLIC_SHOW_USN,
        "period_label": "Overall · All time" if mode == "overall" else date(int(month[:4]), int(month[5:]), 1).strftime("%B %Y"),
    }
    return render(request, "leaderboard/index.html", context)
