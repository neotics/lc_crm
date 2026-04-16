from django.contrib.auth.hashers import make_password
from django.db import migrations


TEACHER_CREDENTIALS = {
    "Ali Yuldashev": ("ali333", "AliYul"),
    "Jasur Yuldashev": ("jasur334", "JasYul"),
    "Madina Karimova": ("madina335", "MadKar"),
    "Akmal Mamatov": ("akmal336", "AkmMam"),
    "Umida Nazarova": ("umida337", "UmiNaz"),
    "Anvar Qodirov": ("anvar338", "AnvQod"),
    "Bekzod Hakimov": ("bekzod339", "BekHak"),
    "Azamat Tursunov": ("azamat340", "AzaTur"),
}


def provision_teacher_accounts(apps, schema_editor):
    User = apps.get_model("auth", "User")
    Teacher = apps.get_model("crm", "Teacher")
    db_alias = schema_editor.connection.alias

    for full_name, (username, password) in TEACHER_CREDENTIALS.items():
        teacher = Teacher.objects.using(db_alias).filter(full_name=full_name).first()
        if teacher is None:
            continue

        existing_user = User.objects.using(db_alias).filter(username=username).first()
        linked_teacher = (
            Teacher.objects.using(db_alias).filter(user=existing_user).first() if existing_user is not None else None
        )

        if teacher.user_id:
            user = teacher.user
            if existing_user is not None and existing_user.pk != user.pk:
                if linked_teacher is not None and linked_teacher.pk != teacher.pk:
                    continue
                user = existing_user
        elif existing_user is not None:
            user = existing_user
        else:
            user = User(username=username)

        parts = full_name.split()
        user.username = username
        user.first_name = parts[0] if parts else ""
        user.last_name = " ".join(parts[1:])
        user.email = user.email or ""
        user.is_staff = False
        user.is_superuser = False
        user.is_active = True
        user.password = make_password(password)
        user.save(using=db_alias)

        teacher.user = user
        teacher.is_active = True
        teacher.save(using=db_alias, update_fields=["user", "is_active", "updated_at"])


class Migration(migrations.Migration):
    dependencies = [
        ("crm", "0005_teacher_user"),
    ]

    operations = [
        migrations.RunPython(provision_teacher_accounts, migrations.RunPython.noop),
    ]
