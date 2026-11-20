# SPARK Ranking System

A Django and SQLite application for managing SPARK members, recording category-wise score transactions, and publishing an all-time or monthly leaderboard.

## Requirements

- Python 3.10 or newer
- Django 5.2 or 6.x
- django-axes (admin login throttling)
- Pillow (for optional member profile image uploads)

## Run on Windows PowerShell

From the project folder:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
$env:SPARK_DEBUG = "true"
$env:SPARK_ALLOWED_HOSTS = "localhost,127.0.0.1"
$env:SPARK_SECRET_KEY = (python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())")
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open `http://127.0.0.1:8000/` for the public leaderboard and `http://127.0.0.1:8000/admin/` to manage members and scores. The migration creates the six required categories. Add members and award transactions in Django Admin; the public page contains no sample records.

To run the automated checks:

```powershell
python manage.py test
python manage.py check
```

## Scoring and ranking rules

- Score entries are the source of truth. A member's total is calculated from the six category totals; totals are never edited independently.
- Every transaction has a member, category, signed point amount, explanation, awarding administrator, award date, and monthly ranking period.
- Score history is append-only in Admin. Existing entries cannot be edited or deleted. Correct a mistake with a clearly explained transaction of the opposite amount.
- Point amounts are stored as decimal text and parsed as Python arbitrary-precision integers. This avoids SQLite's signed 64-bit integer ceiling and defines no application point cap.
- Overall rankings include all transactions. Monthly rankings use the score entry's award date; every month from the earliest member join date through the current month remains selectable, including months with no awards.
- Active members with no score entries appear with zero points. Inactive members and their history are retained but omitted from the public leaderboard.
- Ties are ordered by total points, then skill points, project points, event points, then USN ascending (case-insensitive). This last rule makes list positions repeatable and never changes anyone's score.
- Search, semester, and team filters are applied after ranking, so a filtered view retains each member's position in the full active roster.

## Public USN setting

USNs are hidden on the public page by default. Only show them after club leadership has approved public display. In PowerShell, set the environment variable before starting Django:

```powershell
$env:SPARK_PUBLIC_SHOW_USN = "true"
python manage.py runserver
```

Set it to `false` (or remove it) to keep USNs private. With USNs hidden, the public search only checks member names.

## Deployment notes

Outside debug mode, startup requires `SPARK_SECRET_KEY` and `SPARK_ALLOWED_HOSTS`; there is no built-in production fallback key. Set `SPARK_DEBUG=false`, configure the application and reverse proxy for HTTPS, and run `python manage.py check --deploy`. Production defaults redirect HTTP to HTTPS, mark session and CSRF cookies secure, and send a one-year HSTS policy. Set `SPARK_TRUST_X_FORWARDED_PROTO=true` only when a trusted proxy strips client-supplied `X-Forwarded-Proto` and sets that header itself. HSTS applies to the current host; Django's deploy check will still advise enabling subdomain-wide HSTS and preload. Those stay off until every affected host is confirmed HTTPS-only.

Django Admin login is throttled after five failed attempts from one client IP in a rolling 15-minute window. Direct connections use the socket peer IP. If Django is behind a reverse proxy, set `SPARK_AXES_TRUST_X_FORWARDED_FOR=true` and `SPARK_AXES_PROXY_COUNT` only after the proxy strips client-supplied `X-Forwarded-For`, sets the header itself, and Django is reachable only through the configured number of trusted proxy hops. Multi-factor authentication is not configured; add MFA or restrict `/admin/` to a VPN or approved IP ranges before public exposure. Run `python manage.py migrate` after installing dependencies so the Axes tracking tables are created.

Run `python manage.py collectstatic` and configure the production web server to serve static and uploaded media files. SQLite is suitable for a small club deployment; move to PostgreSQL through Django's database settings if the system grows. The project exposes a server-rendered leaderboard and Django Admin; it contains no API endpoints or API-key authentication layer.
