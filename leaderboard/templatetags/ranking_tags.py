from django import template

from leaderboard.number_fields import format_points


register = template.Library()


@register.filter
def points(value):
    return format_points(value or 0)
