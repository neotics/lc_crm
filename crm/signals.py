from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Attendance, Grade, Lesson, Payment
from .services import ScoringService


@receiver(post_save, sender=Attendance)
def attendance_saved(sender, instance: Attendance, **kwargs):
    ScoringService.recalculate_from_student(instance.student)


@receiver(post_save, sender=Grade)
def grade_saved(sender, instance: Grade, **kwargs):
    ScoringService.recalculate_from_student(instance.student)


@receiver(post_save, sender=Payment)
def payment_saved(sender, instance: Payment, **kwargs):
    ScoringService.recalculate_from_student(instance.student)


@receiver(post_save, sender=Lesson)
def lesson_saved(sender, instance: Lesson, **kwargs):
    for enrollment in instance.course.enrollments.select_related("student"):
        ScoringService.recalculate_from_student(enrollment.student)
