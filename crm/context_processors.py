from .i18n import SUPPORTED_LANGUAGES
from .roles import get_teacher_profile, is_admin_user


def interface_preferences(request):
    user = getattr(request, "user", None)
    current_teacher = get_teacher_profile(user)
    return {
        "current_language": getattr(request, "site_language", "uz"),
        "current_theme": getattr(request, "site_theme", "light"),
        "site_languages": SUPPORTED_LANGUAGES,
        "current_teacher": current_teacher,
        "is_admin_user": is_admin_user(user),
        "is_teacher_user": current_teacher is not None,
    }
