# LC CRM

O'quv markaz uchun Django va Django REST Framework asosidagi minimal CRM.

## Ishga tushirish

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

## ML training

```bash
python manage.py seed_demo_data --students 100 --teachers 8 --courses 12 --reset
python manage.py migrate
python manage.py train_score_model
```

- Student model `artifacts/student_score_model.json` ga saqlanadi.
- Teacher model `artifacts/teacher_score_model.json` ga saqlanadi.
- Student va teacher score hisobida rule-based metrikalar feature sifatida olinadi va ML prediction bilan blend qilinadi.
- Seed demo dataset supervised label maydonlarini ham to'ldiradi: `observed_outcome_score`.
- Admin analytics sahifasida model metrikalari ko'rinadi va retrain tugmasi bor.
- Hozirgi demo dataset synthetic bo'lgani uchun ML model synthetic observed label'lardan o'rganadi, production-ready risk model emas.

## API

- `GET /api/students/<id>/score`
- `GET /api/teachers/<id>/score`
- `GET /api/analytics/top-students`
- `GET /api/analytics/risky-students`
- `GET /api/analytics/teacher-ranking`

## Website sahifalari

- `/login/` - tizimga kirish
- `/` - asosiy dashboard
- `/students/` - studentlar ro'yxati
- `/students/<id>/` - student detail
- `/teachers/` - teacherlar ro'yxati
- `/teachers/<id>/` - teacher detail
- `/courses/` - course ro'yxati
- `/courses/<id>/` - course detail
- `/analytics/` - analytics overview
- `/admin/analytics-dashboard/` - admin analytics

## Eslatma

- Scoring og'irliklari `ScoringConfig` orqali admin panelda o'zgaradi.
- So'nggi 30 kunlik ma'lumot asosida hisoblanadi.
- Faollik bo'lmasa score vaqt o'tishi bilan kamayadi.
- Website qismi Django template asosida yozilgan.
- ML yoqilgan bo'lsa `StudentScore.total_score` ML prediction bilan blend qilingan qiymat bo'ladi.
