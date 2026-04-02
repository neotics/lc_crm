import random
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from crm.models import (
    Attendance,
    Course,
    Enrollment,
    Grade,
    Lesson,
    Payment,
    ScoringConfig,
    Student,
    StudentScore,
    Teacher,
    TeacherScore,
)
from crm.services import ScoringService


class Command(BaseCommand):
    help = "Populate the database with demo CRM data."

    male_first_names = [
        "Ali",
        "Vali",
        "Hasan",
        "Husan",
        "Jasur",
        "Dilshod",
        "Bekzod",
        "Sarvar",
        "Asad",
        "Muhammad",
        "Oybek",
        "Sardor",
        "Azamat",
        "Rustam",
        "Temur",
        "Yusuf",
        "Akmal",
        "Sherzod",
        "Doniyor",
        "Botir",
        "Ulugbek",
        "Jamshid",
        "Anvar",
        "Zafar",
    ]
    female_first_names = [
        "Aziza",
        "Madina",
        "Shahzoda",
        "Nilufar",
        "Komila",
        "Nozima",
        "Zarina",
        "Umida",
        "Malika",
        "Sevara",
        "Sabina",
        "Kamila",
        "Nargiza",
        "Diana",
        "Alina",
        "Mohira",
        "Gulnoza",
        "Shahnoza",
        "Feruza",
        "Nigina",
        "Dilnoza",
        "Lola",
        "Munisa",
    ]
    uzbek_surnames_male = [
        "Karimov",
        "Tursunov",
        "Valiyev",
        "Aliyev",
        "Saidov",
        "Rasulov",
        "Qodirov",
        "Nazarov",
        "Usmonov",
        "Mamatov",
        "Xudoyberdiyev",
        "Yuldashev",
        "Hakimov",
        "Ergashev",
        "Abdullayev",
    ]
    uzbek_surnames_female = [
        "Karimova",
        "Tursunova",
        "Valiyeva",
        "Aliyeva",
        "Saidova",
        "Rasulova",
        "Qodirova",
        "Nazarova",
        "Usmonova",
        "Mamatova",
        "Xudoyberdiyeva",
        "Yuldasheva",
        "Hakimova",
        "Ergasheva",
        "Abdullayeva",
    ]
    course_names = [
        "IELTS Foundation",
        "IELTS Advanced",
        "General English",
        "Kids English",
        "Russian Speaking Club",
        "Math Olympiad",
        "Frontend Bootcamp",
        "Python Backend",
        "SAT Math",
        "Grammar Intensive",
        "Speaking Mastery",
        "Computer Literacy",
    ]
    lesson_topics = [
        "Attendance and warm-up",
        "Grammar practice",
        "Vocabulary builder",
        "Speaking drill",
        "Mock test review",
        "Listening practice",
        "Problem solving",
        "Project workshop",
        "Revision lesson",
        "Performance check",
    ]

    def add_arguments(self, parser):
        parser.add_argument("--students", type=int, default=100)
        parser.add_argument("--teachers", type=int, default=8)
        parser.add_argument("--courses", type=int, default=12)
        parser.add_argument("--reset", action="store_true")
        parser.add_argument("--seed", type=int, default=42)

    def handle(self, *args, **options):
        random.seed(options["seed"])

        with transaction.atomic():
            if options["reset"]:
                self._reset_data()

            config, _ = ScoringConfig.objects.get_or_create(
                id=1,
                defaults={
                    "attendance_weight": 0.3,
                    "grade_weight": 0.3,
                    "payment_weight": 0.2,
                    "activity_weight": 0.2,
                },
            )

            teachers = self._create_teachers(options["teachers"])
            students = self._create_students(options["students"])
            courses = self._create_courses(options["courses"], teachers)
            enrollments = self._create_enrollments(students, courses)
            lessons = self._create_lessons(courses)
            attendance_count, grade_count = self._create_attendance_and_grades(enrollments, lessons)
            payment_count = self._create_payments(students)
            self._recalculate_scores(students, teachers)
            self._apply_supervised_labels(students, teachers)

        self.stdout.write(
            self.style.SUCCESS(
                f"Demo data created: {len(teachers)} teachers, {len(students)} students, "
                f"{len(courses)} courses, {len(enrollments)} enrollments, {len(lessons)} lessons, "
                f"{attendance_count} attendance records, {grade_count} grades, {payment_count} payments."
            )
        )

    def _reset_data(self):
        Attendance.objects.all().delete()
        Grade.objects.all().delete()
        Payment.objects.all().delete()
        Lesson.objects.all().delete()
        Enrollment.objects.all().delete()
        Course.objects.all().delete()
        TeacherScore.objects.all().delete()
        Student.objects.all().delete()
        Teacher.objects.all().delete()

    def _random_full_name(self):
        gender = random.choice(["male", "female"])
        if gender == "male":
            first_name = random.choice(self.male_first_names)
            surname = random.choice(self.uzbek_surnames_male)
        else:
            first_name = random.choice(self.female_first_names)
            surname = random.choice(self.uzbek_surnames_female)
        return f"{first_name} {surname}"

    def _random_phone(self, prefix="90"):
        return f"+998{prefix}{random.randint(1000000, 9999999)}"

    def _create_teachers(self, count: int):
        teachers = []
        for _ in range(count):
            teachers.append(
                Teacher(
                    full_name=self._random_full_name(),
                    phone=self._random_phone(prefix=random.choice(["90", "91", "93", "94"])),
                    is_active=True,
                )
            )
        Teacher.objects.bulk_create(teachers)
        teachers = list(Teacher.objects.order_by("-id")[:count])

        for teacher in teachers:
            TeacherScore.objects.update_or_create(
                teacher=teacher,
                defaults={"feedback_score": random.randint(70, 98)},
            )
        return teachers

    def _create_students(self, count: int):
        today = timezone.localdate()
        students = []
        for index in range(count):
            profile = self._student_profile(index, count)
            students.append(
                Student(
                    full_name=self._random_full_name(),
                    phone=self._random_phone(prefix=random.choice(["95", "97", "98", "99"])),
                    joined_at=today - timedelta(days=random.randint(profile["joined_min"], profile["joined_max"])),
                    is_active=True,
                )
            )
        Student.objects.bulk_create(students)
        return list(Student.objects.order_by("-id")[:count])

    def _create_courses(self, count: int, teachers):
        today = timezone.localdate()
        courses = []
        for index in range(count):
            teacher = teachers[index % len(teachers)]
            courses.append(
                Course(
                    name=f"{self.course_names[index % len(self.course_names)]} #{index + 1}",
                    teacher=teacher,
                    start_date=today - timedelta(days=random.randint(20, 120)),
                    is_active=True,
                )
            )
        Course.objects.bulk_create(courses)
        return list(Course.objects.order_by("-id")[:count])

    def _create_enrollments(self, students, courses):
        today = timezone.localdate()
        enrollments = []
        used_pairs = set()
        shuffled_students = students[:]
        random.shuffle(shuffled_students)
        student_profiles = self._build_profile_map_for_students(students)

        for student in shuffled_students:
            profile = student_profiles.get(student.id, "steady")
            course_count = random.randint(1, min(3, len(courses)))
            if profile == "risky":
                course_count = 1
            student_courses = random.sample(courses, course_count)
            for course in student_courses:
                pair = (student.id, course.id)
                if pair in used_pairs:
                    continue
                used_pairs.add(pair)
                if profile == "risky":
                    status = random.choices(
                        [Enrollment.Status.DROPPED, Enrollment.Status.ACTIVE, Enrollment.Status.COMPLETED],
                        weights=[0.70, 0.15, 0.15],
                        k=1,
                    )[0]
                elif profile == "strong":
                    status = random.choices(
                        [Enrollment.Status.ACTIVE, Enrollment.Status.COMPLETED, Enrollment.Status.DROPPED],
                        weights=[0.84, 0.12, 0.04],
                        k=1,
                    )[0]
                else:
                    status = random.choices(
                        [Enrollment.Status.ACTIVE, Enrollment.Status.COMPLETED, Enrollment.Status.DROPPED],
                        weights=[0.75, 0.15, 0.10],
                        k=1,
                    )[0]
                left_on = None
                if status == Enrollment.Status.DROPPED:
                    if profile == "risky":
                        left_on = today - timedelta(days=random.randint(35, 75))
                    else:
                        left_on = today - timedelta(days=random.randint(1, 25))
                enrollments.append(
                    Enrollment(
                        student=student,
                        course=course,
                        status=status,
                        enrolled_on=max(student.joined_at, course.start_date),
                        left_on=left_on,
                    )
                )

        Enrollment.objects.bulk_create(enrollments)
        return enrollments

    def _create_lessons(self, courses):
        today = timezone.localdate()
        lessons = []
        for course in courses:
            lesson_total = random.randint(8, 12)
            for offset in range(lesson_total):
                lesson_date = today - timedelta(days=lesson_total * 3 - offset * 3)
                lessons.append(
                    Lesson(
                        course=course,
                        date=lesson_date,
                        topic=random.choice(self.lesson_topics),
                    )
                )
        Lesson.objects.bulk_create(lessons)
        return list(Lesson.objects.select_related("course").all())

    def _create_attendance_and_grades(self, enrollments, lessons):
        lessons_by_course = {}
        for lesson in lessons:
            lessons_by_course.setdefault(lesson.course_id, []).append(lesson)

        student_profiles = self._build_student_profiles()
        attendance_records = []
        grade_records = []
        for enrollment in enrollments:
            course_lessons = lessons_by_course.get(enrollment.course_id, [])
            if not course_lessons:
                continue

            profile = student_profiles.get(enrollment.student_id, "steady")

            allowed_lessons = [lesson for lesson in course_lessons if lesson.date >= enrollment.enrolled_on]
            if enrollment.left_on:
                allowed_lessons = [lesson for lesson in allowed_lessons if lesson.date <= enrollment.left_on]

            for lesson in allowed_lessons:
                status = self._attendance_status_for_profile(profile)
                attendance_records.append(
                    Attendance(
                        lesson=lesson,
                        student=enrollment.student,
                        status=status,
                    )
                )
                if status != Attendance.Status.ABSENT:
                    grade_records.append(
                        Grade(
                            student=enrollment.student,
                            lesson=lesson,
                            grade=self._grade_for_profile(profile),
                        )
                    )

        Attendance.objects.bulk_create(attendance_records)
        Grade.objects.bulk_create(grade_records)
        return len(attendance_records), len(grade_records)

    def _create_payments(self, students):
        today = timezone.localdate()
        base_month = today.replace(day=1)
        months = []
        for index in range(3):
            month = base_month - timedelta(days=30 * index)
            months.append(month.replace(day=1))

        payments = []
        student_profiles = self._build_student_profiles()
        for student in students:
            monthly_fee = Decimal(str(random.choice([450000, 500000, 550000, 600000])))
            debt_pattern = self._payment_pattern_for_profile(student_profiles.get(student.id, "steady"))

            for idx, month in enumerate(months):
                amount_paid = monthly_fee
                status = Payment.Status.PAID

                if debt_pattern == "one_debt" and idx == 0:
                    amount_paid = monthly_fee * Decimal("0.55")
                    status = Payment.Status.PARTIAL
                elif debt_pattern == "multi_debt" and idx in (0, 1):
                    if idx == 0:
                        amount_paid = monthly_fee * Decimal("0.40")
                        status = Payment.Status.PARTIAL
                    else:
                        amount_paid = Decimal("0.00")
                        status = Payment.Status.UNPAID

                payments.append(
                    Payment(
                        student=student,
                        month=month,
                        amount_due=monthly_fee,
                        amount_paid=amount_paid.quantize(Decimal("0.01")),
                        status=status,
                    )
                )

        Payment.objects.bulk_create(payments)
        return len(payments)

    def _recalculate_scores(self, students, teachers):
        for student in students:
            ScoringService.recalculate_student_score(student)
        for teacher in teachers:
            ScoringService.recalculate_teacher_score(teacher)

    def _apply_supervised_labels(self, students, teachers):
        student_profiles = self._build_profile_map_for_students(students)
        for student in students:
            score = StudentScore.objects.get(student=student)
            profile = student_profiles.get(student.id, "steady")
            observed_outcome = self._observed_student_outcome(profile, score.rule_based_score or score.total_score)
            score.observed_outcome_score = observed_outcome
            score.observed_risk_level = ScoringService.determine_risk_level(observed_outcome)
            score.save(update_fields=["observed_outcome_score", "observed_risk_level", "updated_at"])

        teacher_profiles = self._build_teacher_profiles(teachers)
        for teacher in teachers:
            score = TeacherScore.objects.get(teacher=teacher)
            observed_outcome = self._observed_teacher_outcome(teacher_profiles.get(teacher.id, "steady"), score)
            score.observed_outcome_score = observed_outcome
            score.save(update_fields=["observed_outcome_score", "updated_at"])

    def _student_profile(self, index: int, total: int):
        risky_cutoff = max(12, total // 5)
        strong_cutoff = max(20, total // 4)
        if index < risky_cutoff:
            return {"kind": "risky", "joined_min": 45, "joined_max": 180}
        if index < risky_cutoff + strong_cutoff:
            return {"kind": "strong", "joined_min": 20, "joined_max": 120}
        return {"kind": "steady", "joined_min": 15, "joined_max": 150}

    def _build_student_profiles(self):
        students = list(Student.objects.order_by("-id"))
        profiles = {}
        total = len(students)
        for index, student in enumerate(students):
            profiles[student.id] = self._student_profile(index, total)["kind"]
        return profiles

    def _build_profile_map_for_students(self, students):
        profiles = {}
        total = len(students)
        for index, student in enumerate(students):
            profiles[student.id] = self._student_profile(index, total)["kind"]
        return profiles

    def _attendance_status_for_profile(self, profile: str):
        if profile == "strong":
            weights = [0.75, 0.14, 0.06, 0.05]
        elif profile == "risky":
            weights = [0.28, 0.10, 0.07, 0.55]
        else:
            weights = [0.58, 0.14, 0.08, 0.20]
        return random.choices(
            [
                Attendance.Status.PRESENT,
                Attendance.Status.LATE,
                Attendance.Status.EXCUSED,
                Attendance.Status.ABSENT,
            ],
            weights=weights,
            k=1,
        )[0]

    def _grade_for_profile(self, profile: str):
        if profile == "strong":
            return random.randint(82, 100)
        if profile == "risky":
            return random.randint(45, 68)
        return random.randint(60, 88)

    def _payment_pattern_for_profile(self, profile: str):
        if profile == "strong":
            return "clean"
        if profile == "risky":
            return random.choice(["one_debt", "multi_debt"])
        return random.choices(
            ["clean", "one_debt", "multi_debt"],
            weights=[0.55, 0.25, 0.20],
            k=1,
        )[0]

    def _observed_student_outcome(self, profile: str, baseline: float) -> float:
        if profile == "strong":
            delta = random.uniform(-3, 4)
            return ScoringService.clamp(max(76.0, baseline + delta))
        if profile == "risky":
            delta = random.uniform(-8, 1)
            return ScoringService.clamp(min(48.0, baseline + delta))
        delta = random.uniform(-5, 5)
        return ScoringService.clamp(min(74.0, max(50.0, baseline + delta)))

    def _build_teacher_profiles(self, teachers):
        teacher_profiles = {}
        for teacher in teachers:
            students = list(ScoringService.teacher_students_queryset(teacher))
            if not students:
                teacher_profiles[teacher.id] = "steady"
                continue
            student_profiles = self._build_profile_map_for_students(students)
            risky_count = sum(1 for value in student_profiles.values() if value == "risky")
            strong_count = sum(1 for value in student_profiles.values() if value == "strong")
            if risky_count >= strong_count and risky_count > 0:
                teacher_profiles[teacher.id] = "risky"
            elif strong_count > risky_count:
                teacher_profiles[teacher.id] = "strong"
            else:
                teacher_profiles[teacher.id] = "steady"
        return teacher_profiles

    def _observed_teacher_outcome(self, profile: str, score: TeacherScore) -> float:
        baseline = score.rule_based_score or score.total_score
        if profile == "strong":
            return ScoringService.clamp(max(78.0, baseline + random.uniform(-2, 4)))
        if profile == "risky":
            return ScoringService.clamp(min(56.0, baseline + random.uniform(-10, 1)))
        return ScoringService.clamp(baseline + random.uniform(-4, 4))
