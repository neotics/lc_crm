from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("crm", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="scoringconfig",
            name="ml_blend_weight",
            field=models.FloatField(default=0.7),
        ),
        migrations.AddField(
            model_name="scoringconfig",
            name="ml_enabled",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="scoringconfig",
            name="ml_min_training_rows",
            field=models.PositiveIntegerField(default=30),
        ),
        migrations.AddField(
            model_name="studentscore",
            name="ml_confidence",
            field=models.FloatField(default=0.0),
        ),
        migrations.AddField(
            model_name="studentscore",
            name="ml_predicted_score",
            field=models.FloatField(default=0.0),
        ),
        migrations.AddField(
            model_name="studentscore",
            name="rule_based_score",
            field=models.FloatField(default=0.0),
        ),
        migrations.AddField(
            model_name="studentscore",
            name="score_source",
            field=models.CharField(
                choices=[("rule_based", "Rule based"), ("ml_blended", "ML blended")],
                default="rule_based",
                max_length=20,
            ),
        ),
    ]
