from rest_framework import serializers

from .models import StudentScore, TeacherScore


class StudentScoreSerializer(serializers.ModelSerializer):
    student_id = serializers.IntegerField(source="student.id", read_only=True)
    student_name = serializers.CharField(source="student.full_name", read_only=True)

    class Meta:
        model = StudentScore
        fields = [
            "student_id",
            "student_name",
            "attendance_score",
            "grade_score",
            "payment_score",
            "activity_score",
            "rule_based_score",
            "ml_predicted_score",
            "ml_confidence",
            "observed_outcome_score",
            "observed_risk_level",
            "score_source",
            "total_score",
            "risk_level",
            "last_activity_at",
            "last_updated",
        ]


class TeacherScoreSerializer(serializers.ModelSerializer):
    teacher_id = serializers.IntegerField(source="teacher.id", read_only=True)
    teacher_name = serializers.CharField(source="teacher.full_name", read_only=True)

    class Meta:
        model = TeacherScore
        fields = [
            "teacher_id",
            "teacher_name",
            "student_avg_score",
            "attendance_control_score",
            "student_retention_score",
            "feedback_score",
            "rule_based_score",
            "ml_predicted_score",
            "ml_confidence",
            "observed_outcome_score",
            "score_source",
            "total_score",
            "last_updated",
        ]
