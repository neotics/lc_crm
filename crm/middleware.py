from .i18n import normalize_language, normalize_theme


class InterfacePreferenceMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.site_language = normalize_language(request.GET.get("lang") or request.COOKIES.get("site_lang"))
        request.site_theme = normalize_theme(request.GET.get("theme") or request.COOKIES.get("site_theme"))
        response = self.get_response(request)
        response.set_cookie("site_lang", request.site_language, max_age=60 * 60 * 24 * 365)
        response.set_cookie("site_theme", request.site_theme, max_age=60 * 60 * 24 * 365)
        return response
