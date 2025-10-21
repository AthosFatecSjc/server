"""Filtros personalizados para templates Django."""

from django.template import Library

register = Library()


@register.filter
def get_item(dictionary, key):
    """Retorna o valor de um dicionário dado uma chave."""
    return dictionary.get(key)
