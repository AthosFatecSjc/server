from django import template

register = template.Library()


@register.filter
def split(value, separator=" "):
    """
    Divide uma string em uma lista usando o separador fornecido.
    Exemplo de uso no template:
    {% for item in "JAN FEV MAR"|split %}
        {{ item }}
    {% endfor %}
    """
    if not isinstance(value, str):
        return value
    return value.split(separator)
