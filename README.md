# Job Recommender Platform

A Django-based job discovery and recommendation platform prototype. It contains core job models and a matching/recommendation engine, ingestion tools for CSV data, admin and dashboard views, and notification and interaction apps.

## Features

- Role-based job platform (candidates, employers, admins)
- Job ingestion from CSV sources
- Candidate recommendations / matching engine
- Employer verification and admin dashboard
- Notifications and alerts
- Modular Django apps split under `apps/`

## Tech stack

- Python 3.10+ (or compatible)
- Django
- SQLite (development) — production DB configurable in settings
- Frontend: standard Django templates, static assets under `static/`

## Repo layout

- `apps/` — Django apps (accounts, jobs, recommendations, dashboard, ingestion, interactions, notifications, etc.)
- `config/` — Django project configuration and `settings.py`
- `templates/` — HTML templates
- `static/` — CSS, JS, images
- `media/` — uploaded media (avatars, ingestion CSVs)

See configuration at [config/settings.py](config/settings.py).

## Quickstart (development)

Prerequisites

- Python 3.10+ installed
- Recommended: create a virtual environment

On macOS / Linux / Windows (Git Bash / WSL) run:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Environment variables

A `config/.env` file is included for local development (check `config/.env`). Make sure the following values are set (or created) before running in development or production:

- `SECRET_KEY` — Django secret
- `DEBUG` — `True` or `False`
- `ALLOWED_HOSTS` — comma-separated hosts
- Database configuration variables (if not using the default SQLite)

If you need a simple `.env` example:

```
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
```

Database & migrations

```bash
python manage.py migrate
python manage.py createsuperuser
```

Collect static (for production)

```bash
python manage.py collectstatic
```

Run the development server

```bash
python manage.py runserver
```

Open http://127.0.0.1:8000/ in your browser.

## Testing

Run the test suite:

```bash
python manage.py test
```

## Ingestion

CSV ingestion helpers are located in `apps/ingestion/` and referenced by templates and admin forms. CSV files used by ingestion can be put under `media/ingestion/csv/`.

## Recommendations / Matching engine

The recommendation engine lives in `apps/recommendations/` (see `matching_engine.py`). Review its tests for expected behavior.

## Static & Media files

- Static files: `static/`
- User uploads and generated media: `media/`

Ensure your production `STATIC_ROOT` and `MEDIA_ROOT` are configured in `config/settings.py` before deployment.

## Deployment notes

- Use a production-ready database (Postgres, MySQL) and update `config/settings.py` or provide a `DATABASE_URL`.
- Configure a WSGI server (Gunicorn/Uvicorn) and a reverse proxy (nginx or similar).
- Serve static files from a CDN or web server (or run `collectstatic`).
- Secure environment variables (use secrets manager or OS env vars in production).

## Contributing

- Create issues for bugs or requested features.
- Open pull requests with tests and clear descriptions.

## Useful files

- `requirements.txt` — Python dependencies
- `manage.py` — Django CLI entrypoint
- `config/settings.py` — main Django settings

## Contact

If you want help running or deploying the project, open an issue or contact the repository owner (Eleazar Toto).

---


