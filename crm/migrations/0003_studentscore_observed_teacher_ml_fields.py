from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("crm", "0002_studentscore_ml_fields_scoringconfig_ml"),
    ]

    operations = [
        migrations.AddField(
            model_name="studentscore",
            name="observed_outcome_score",
            field=models.FloatField(default=0.0),
        ),
        migrations.AddField(
            model_name="studentscore",
            name="observed_risk_level",
            field=models.CharField(
                choices=[("low", "Low"), ("medium", "Medium"), ("high", "High")],
                default="high",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="teacherscore",
            name="ml_confidence",
            field=models.FloatField(default=0.0),
        ),
        migrations.AddField(
            model_name="teacherscore",
            name="ml_predicted_score",
            field=models.FloatField(default=0.0),
        ),
        migrations.AddField(
            model_name="teacherscore",
            name="observed_outcome_score",
            field=models.FloatField(default=0.0),
        ),
        migrations.AddField(
            model_name="teacherscore",
            name="rule_based_score",
            field=models.FloatField(default=0.0),
        ),
        migrations.AddField(
            model_name="teacherscore",
            name="score_source",
            field=models.CharField(
                choices=[("rule_based", "Rule based"), ("ml_blended", "ML blended")],
                default="rule_based",
                max_length=20,
            ),
        ),
    ]
