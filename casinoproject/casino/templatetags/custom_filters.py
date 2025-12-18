from django import template

register = template.Library()

@register.filter
def index(indexable, i):
    """リストのインデックスアクセス"""
    try:
        return indexable[int(i)]
    except (IndexError, TypeError, ValueError):
        return None