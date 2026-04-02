from .i18n import SUPPORTED_LANGUAGES


def interface_preferences(request):
    return {
        "current_language": getattr(request, "site_language", "uz"),
        "current_theme": getattr(request, "site_theme", "light"),
        "site_languages": SUPPORTED_LANGUAGES,
    }
