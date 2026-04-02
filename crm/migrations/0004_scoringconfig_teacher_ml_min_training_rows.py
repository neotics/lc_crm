from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("crm", "0003_studentscore_observed_teacher_ml_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="scoringconfig",
            name="teacher_ml_min_training_rows",
            field=models.PositiveIntegerField(default=5),
        ),
    ]
