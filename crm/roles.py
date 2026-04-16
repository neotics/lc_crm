from django.contrib.auth.models import AnonymousUser


def get_teacher_profile(user):
    if not user or isinstance(user, AnonymousUser) or not user.is_authenticated:
        return None
    try:
        teacher = user.teacher_profile
    except AttributeError:
        return None
    return teacher if teacher.is_active else None


def is_admin_user(user) -> bool:
    return bool(user and user.is_authenticated and (user.is_staff or user.is_superuser))


def is_teacher_user(user) -> bool:
    return get_teacher_profile(user) is not None


def has_crm_access(user) -> bool:
    return is_admin_user(user) or is_teacher_user(user)


def filter_students_for_user(queryset, user):
    if is_admin_user(user):
        return queryset

    teacher = get_teacher_profile(user)
    if not teacher:
        return queryset.none()

    return queryset.filter(enrollments__course__teacher=teacher).distinct()


def filter_courses_for_user(queryset, user):
    if is_admin_user(user):
        return queryset

    teacher = get_teacher_profile(user)
    if not teacher:
        return queryset.none()

    return queryset.filter(teacher=teacher)


def filter_teachers_for_user(queryset, user):
    if is_admin_user(user):
        return queryset

    teacher = get_teacher_profile(user)
    if not teacher:
        return queryset.none()

    return queryset.filter(pk=teacher.pk)
