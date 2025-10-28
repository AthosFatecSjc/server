"""Filtros customizados para templates do dashboard."""

import json

from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter(name="jsonify")
def jsonify(value):
    """
    Converte um objeto Python para JSON e marca como seguro para HTML.

    Args:
        value: Objeto Python a ser convertido para JSON

    Returns:
        String JSON marcada como segura para HTML
    """
    return mark_safe(json.dumps(value))
