from django import template

register = template.Library()


@register.filter
def format_rut(value):
    if not value:
        return "Pendiente"
    if "-" not in str(value):
        return value
    body, check_digit = str(value).rsplit("-", 1)
    return f"{int(body):,}".replace(",", ".") + f"-{check_digit}"
