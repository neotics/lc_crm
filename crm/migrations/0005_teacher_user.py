from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("crm", "0004_scoringconfig_teacher_ml_min_training_rows"),
    ]

    operations = [
        migrations.AddField(
            model_name="teacher",
            name="user",
            field=models.OneToOneField(
                blank=True,
                help_text="Teacher login qilishi uchun bog'langan user account.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="teacher_profile",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
