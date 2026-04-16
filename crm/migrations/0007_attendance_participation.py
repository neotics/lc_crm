from django.db import migrations, models


def set_absent_participation(apps, schema_editor):
    Attendance = apps.get_model("crm", "Attendance")
    Attendance.objects.using(schema_editor.connection.alias).filter(status="absent").update(participation="none")


class Migration(migrations.Migration):
    dependencies = [
        ("crm", "0006_provision_teacher_accounts"),
    ]

    operations = [
        migrations.AddField(
            model_name="attendance",
            name="participation",
            field=models.CharField(
                choices=[
                    ("high", "High"),
                    ("medium", "Medium"),
                    ("low", "Low"),
                    ("none", "None"),
                ],
                default="medium",
                max_length=20,
            ),
        ),
        migrations.RunPython(set_absent_participation, migrations.RunPython.noop),
    ]
