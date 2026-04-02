# LC CRM

CRM-система для учебного центра на базе Django и Django REST Framework.

Проект включает:
- backend для управления студентами, преподавателями, курсами, посещаемостью, оценками и оплатами
- веб-интерфейс на Django Templates
- систему скоринга студентов и преподавателей
- аналитические страницы и админ-панель
- ML-модуль для обучения моделей и расчета blended score

## О проекте

Система предназначена для учебных центров, где нужно не только хранить данные, но и оценивать:
- успеваемость студентов
- уровень риска потери студента
- качество работы преподавателей
- влияние посещаемости, оплат и активности на общий результат

В проекте реализованы два уровня оценки:
- `rule-based scoring` — формульный расчет по заданным весам
- `ML-blended scoring` — итоговый score с учетом предсказания обученной модели

## Основные возможности

### 1. CRM сущности

В системе есть следующие основные модели:
- `Student`
- `Teacher`
- `Course`
- `Enrollment`
- `Lesson`
- `Attendance`
- `Grade`
- `Payment`
- `StudentScore`
- `TeacherScore`
- `ScoringConfig`

### 2. Система скоринга студентов

Для студентов рассчитываются:
- `attendance_score`
- `grade_score`
- `payment_score`
- `activity_score`
- `rule_based_score`
- `ml_predicted_score`
- `total_score`
- `risk_level`

Логика расчета строится на данных за последние 30 дней:
- посещаемость
- оценки
- оплаты
- активность

Уровни риска:
- `low`
- `medium`
- `high`

### 3. Система скоринга преподавателей

Для преподавателей рассчитываются:
- `student_avg_score`
- `attendance_control_score`
- `student_retention_score`
- `feedback_score`
- `rule_based_score`
- `ml_predicted_score`
- `total_score`

Оценка преподавателя зависит от:
- среднего результата его студентов
- полноты контроля посещаемости
- удержания студентов
- ручной оценки администратора

### 4. Автоматический пересчет

Скоринг обновляется автоматически через Django signals после изменений в:
- `Attendance`
- `Grade`
- `Payment`
- `Lesson`

Это позволяет поддерживать актуальные данные без ручного пересчета.

### 5. ML-модуль

В проект встроен lightweight ML pipeline.

Он умеет:
- собирать feature-пакеты по студентам и преподавателям
- обучать модель на имеющихся данных
- сохранять артефакты модели в папку `artifacts/`
- использовать предсказание модели в итоговом score

Файлы моделей:
- `artifacts/student_score_model.json`
- `artifacts/teacher_score_model.json`

Важно:
- текущая ML-часть работает на synthetic/demo данных
- это не production-grade Data Science pipeline
- модель обучается на наблюдаемых `observed_outcome_score`, которые генерируются в demo dataset

## Технологии

- Python 3
- Django 5
- Django REST Framework
- SQLite по умолчанию
- WhiteNoise для static файлов
- Gunicorn для production
- dj-database-url для подключения к PostgreSQL или другой БД через `DATABASE_URL`

## Структура проекта

```text
LC_CRM/
├── config/                     # Django settings, urls, wsgi, asgi
├── crm/                        # Основное приложение CRM
│   ├── management/commands/    # seed, ML training и другие команды
│   ├── migrations/             # миграции БД
│   ├── templatetags/           # template tags для UI
│   ├── admin.py                # admin-панель и analytics dashboard
│   ├── ml.py                   # ML utility и работа с артефактами
│   ├── models.py               # модели CRM
│   ├── serializers.py          # DRF serializers
│   ├── services.py             # scoring service и бизнес-логика
│   ├── signals.py              # автопересчет score
│   ├── urls.py                 # API routes
│   ├── views.py                # API и web views
│   └── website_urls.py         # маршруты web-интерфейса
├── templates/                  # HTML-шаблоны
├── static/                     # CSS / JS
├── artifacts/                  # сохраненные ML-модели
├── requirements.txt
├── Procfile
├── build.sh
└── render.yaml
```

## Установка и запуск локально

### 1. Создание виртуального окружения

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 3. Применение миграций

```bash
python manage.py migrate
```

### 4. Создание администратора

```bash
python manage.py createsuperuser
```

### 5. Запуск локального сервера

```bash
python manage.py runserver
```

После запуска сайт будет доступен по адресу:

```text
http://127.0.0.1:8000/
```

## Заполнение demo-данными

Для быстрого наполнения базы тестовыми данными используется management command:

```bash
python manage.py seed_demo_data --students 100 --teachers 8 --courses 12 --reset
```

Команда создает:
- преподавателей
- студентов
- курсы
- записи на курсы
- уроки
- посещаемость
- оценки
- оплаты
- score-объекты
- supervised observed labels для ML

Параметры:
- `--students` — количество студентов
- `--teachers` — количество преподавателей
- `--courses` — количество курсов
- `--reset` — полная очистка и повторное заполнение

## Обучение ML-моделей

После заполнения demo-данными можно обучить модели:

```bash
python manage.py train_score_model
```

Команда:
- обучает student model
- обучает teacher model
- сохраняет артефакты в `artifacts/`
- пересчитывает blended score для всех записей

## API

В проекте доступны следующие API endpoints:

- `GET /api/students/<id>/score`
- `GET /api/teachers/<id>/score`
- `GET /api/analytics/top-students`
- `GET /api/analytics/risky-students`
- `GET /api/analytics/teacher-ranking`

API использует DRF serializers и рассчитан на интеграцию с внешними frontend-клиентами.

## Веб-интерфейс

Проект уже содержит полноценный web UI.

Основные страницы:
- `/login/` — вход в систему
- `/` — dashboard
- `/students/` — список студентов
- `/students/<id>/` — карточка студента
- `/teachers/` — список преподавателей
- `/teachers/<id>/` — карточка преподавателя
- `/courses/` — список курсов
- `/courses/<id>/` — карточка курса
- `/analytics/` — аналитика
- `/admin/` — стандартная Django admin
- `/admin/analytics-dashboard/` — расширенная analytics-страница администратора

## Интерфейс

В системе есть:
- многоязычность: `uz`, `ru`, `en`
- light/dark mode
- интерактивные dashboard-блоки
- live search
- фильтрация по risk level
- карточки, таблицы и аналитические блоки

## Production / Deploy

Проект подготовлен для деплоя.

Добавлены:
- `gunicorn`
- `whitenoise`
- `dj-database-url`
- `Procfile`
- `build.sh`
- `render.yaml`
- `.env.example`

### Пример env-переменных

```env
SECRET_KEY=change-me
DEBUG=False
ALLOWED_HOSTS=.onrender.com,localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=https://your-app.onrender.com
DATABASE_URL=sqlite:///db.sqlite3
```

### Быстрый деплой на Render

1. Запушить проект на GitHub
2. Создать `Web Service` на Render
3. Подключить репозиторий
4. Указать env variables
5. Запустить deploy

После деплоя желательно выполнить:

```bash
python manage.py createsuperuser
python manage.py seed_demo_data --students 100 --teachers 8 --courses 12 --reset
python manage.py train_score_model
```

## Проверка проекта

Проверка конфигурации:

```bash
python manage.py check
```

Запуск тестов:

```bash
python manage.py test crm
```

## Ограничения текущей реализации

- ML-модель демонстрационная, а не промышленная
- наблюдаемые labels для обучения сейчас synthetic
- SQLite подходит для demo и локальной разработки, для production лучше PostgreSQL
- web UI уже функционален, но при необходимости его можно дополнительно расширить отдельным frontend-приложением

## Что можно улучшить дальше

- перейти на PostgreSQL в production
- добавить Celery для фоновых задач
- вынести ML training в отдельный pipeline
- добавить версионирование моделей
- сохранить историю обучения моделей
- добавить графики feature importance
- внедрить real-world labels вместо synthetic observed outcome

## Авторская идея проекта

Этот проект не просто хранит данные CRM, а пытается превратить их в систему принятия решений:
- кого нужно срочно удержать
- какой студент уходит в риск
- какой преподаватель реально влияет на результат
- где проблема в оплате, посещаемости или академическом прогрессе

Именно поэтому здесь объединены:
- CRM
- scoring engine
- analytics
- ML prediction

