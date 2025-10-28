"""Filtros customizados para templates do dashboard."""

import json

from django import template

register = template.Library()


@register.filter(name="jsonify")
def jsonify(value):
    """
    Converte um objeto Python para JSON.

    Args:
        value: Objeto Python a ser convertido para JSON

    Returns:
        String JSON escapada automaticamente pelo template
    """
    return json.dumps(value)
