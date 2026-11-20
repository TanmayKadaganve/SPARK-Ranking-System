"""Score aggregation and ranking rules."""
from calendar import monthrange
from datetime import date

from .models import CATEGORY_DEFINITIONS, Member, ScoreEntry


CATEGORY_CODES = tuple(code for code, _, _ in CATEGORY_DEFINITIONS)


def month_bounds(month_value):
    """Return inclusive date boundaries for a validated YYYY-MM value."""
    year, month = (int(part) for part in month_value.split("-"))
    start = date(year, month, 1)
    end = date(year, month, monthrange(year, month)[1])
    return start, end


def build_rankings(*, mode="overall", month=None, include_inactive=False):
    """Return every member with category totals and a stable 1-based rank.

    Tie order is total, skills, projects, event wins, then USN ascending.
    Scores themselves are never modified to break a tie.
    """
    members = Member.objects.all()
    if not include_inactive:
        members = members.filter(is_active=True)
    members = list(members)

    totals = {
        member.pk: {code: 0 for code in CATEGORY_CODES}
        for member in members
    }
    entries = ScoreEntry.objects.filter(member_id__in=[m.pk for m in members]).select_related("category")
    if mode == "monthly":
        if not month:
            raise ValueError("A month is required for monthly rankings.")
        start, end = month_bounds(month)
        entries = entries.filter(date_awarded__gte=start, date_awarded__lte=end)
    elif mode != "overall":
        raise ValueError("Ranking mode must be 'overall' or 'monthly'.")

    for member_id, category__code, points in entries.values_list("member_id", "category__code", "points"):
        if category__code in totals[member_id]:
            totals[member_id][category__code] += points

    ranked = [
        {"member": member, "scores": totals[member.pk], "total": sum(totals[member.pk].values())}
        for member in members
    ]
    ranked.sort(
        key=lambda row: (
            -row["total"],
            -row["scores"]["skills"],
            -row["scores"]["projects"],
            -row["scores"]["events"],
            row["member"].usn.casefold(),
        )
    )
    for position, row in enumerate(ranked, start=1):
        row["rank"] = position
    return ranked


def score_breakdown(member, *, mode="overall", month=None):
    result = build_rankings(mode=mode, month=month, include_inactive=True)
    return next(row for row in result if row["member"].pk == member.pk)


def validate_month(value):
    if not value:
        return False
    if len(value) != 7 or value[4] != "-":
        return False
    try:
        year, month = (int(part) for part in value.split("-"))
        return 1 <= month <= 12 and 1 <= year <= 9999
    except (TypeError, ValueError):
        return False
