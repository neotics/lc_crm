from django import template

from crm.i18n import translate

register = template.Library()


@register.simple_tag(takes_context=True)
def tr(context, key: str):
    request = context.get("request")
    lang = getattr(request, "site_language", "uz") if request else "uz"
    return translate(key, lang)


@register.simple_tag(takes_context=True)
def tr_value(context, value: str):
    request = context.get("request")
    lang = getattr(request, "site_language", "uz") if request else "uz"
    return translate(value, lang)
