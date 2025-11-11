"""Custom template filters for usuarios app."""

import re

from django import template
from django.utils.html import escape, strip_tags
from django.utils.safestring import mark_safe

register = template.Library()

_LI_PATTERN = re.compile(r"<li[^>]*>(.*?)</li>", flags=re.IGNORECASE | re.DOTALL)


def _sanitize_item(content: str) -> str:
    clean_text = strip_tags(content).strip()
    return escape(clean_text)


@register.filter(name="render_help_text")
def render_help_text(value: str) -> str:
    if not value:
        return ""

    items = [
        _sanitize_item(chunk) for chunk in _LI_PATTERN.findall(value) if chunk.strip()
    ]
    if items:
        bullet_items = "".join(f"<li>{item}</li>" for item in items if item)
        return mark_safe(f'<ul class="list-disc pl-5">{bullet_items}</ul>')

    return escape(strip_tags(value))
