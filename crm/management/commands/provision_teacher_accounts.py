from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from crm.models import Teacher


class Command(BaseCommand):
    help = "Create login accounts for teachers that do not have a linked user."

    def add_arguments(self, parser):
        parser.add_argument("--password", required=True, help="Password to set for newly created teacher users.")
        parser.add_argument("--prefix", default="teacher", help="Username prefix. Default: teacher")
        parser.add_argument("--include-inactive", action="store_true", help="Include inactive teachers too.")
        parser.add_argument(
            "--reset-existing-passwords",
            action="store_true",
            help="Also reset passwords for teachers that already have a linked user.",
        )
        parser.add_argument("--dry-run", action="store_true", help="Show what would be created without saving changes.")

    def handle(self, *args, **options):
        password = options["password"]
        if len(password) < 8:
            raise CommandError("Password must be at least 8 characters long.")

        teachers = Teacher.objects.select_related("user").order_by("id")
        if not options["include_inactive"]:
            teachers = teachers.filter(is_active=True)

        User = get_user_model()
        created = 0
        updated = 0

        for teacher in teachers:
            if teacher.user_id:
                if options["reset_existing_passwords"]:
                    self.stdout.write(f"Reset password: {teacher.full_name} -> {teacher.user.username}")
                    if not options["dry_run"]:
                        teacher.user.set_password(password)
                        teacher.user.save(update_fields=["password"])
                    updated += 1
                continue

            username = self._unique_username(User, f"{options['prefix']}{teacher.pk}")
            self.stdout.write(f"Create user: {teacher.full_name} -> {username}")
            if not options["dry_run"]:
                user = User.objects.create_user(
                    username=username,
                    password=password,
                    is_staff=False,
                    is_superuser=False,
                )
                teacher.user = user
                teacher.save(update_fields=["user", "updated_at"])
            created += 1

        self.stdout.write(self.style.SUCCESS(f"Done. Created={created}, password_reset={updated}"))

    @staticmethod
    def _unique_username(User, base_username: str) -> str:
        username = base_username
        suffix = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}_{suffix}"
            suffix += 1
        return username
