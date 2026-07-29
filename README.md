# django-fuel-api

A Django-based API for working with fuel route data, including fuel station geocoding utilities and route-related endpoints.

## Repository Structure

- `fuel_route/` — Main Django project root
  - `manage.py` — Django management entry point
  - `fuel_route/` — Django settings/project package
  - `routes/` — App containing route-related logic/endpoints
  - `geocode_stations.py` — Script for geocoding stations
  - `geocode_stations_fast.py` — Faster/batch geocoding variant
  - `db.sqlite3` — Local SQLite database (development)
  - `.env` — Environment variable file (local config)
- `env/` — Local virtual environment directory (should not be committed in production workflows)

## Features

- Django-powered backend API
- Route module for fuel route functionality
- Utility scripts for station geocoding
- SQLite setup for quick local development

## Tech Stack

- Python
- Django
- SQLite (default local database)

## Getting Started

### 1) Clone the repository

```bash
git clone https://github.com/naman089/django-fuel-api.git
cd django-fuel-api
```

### 2) Create and activate a virtual environment

> If you already have one, you can skip this step.

**macOS/Linux**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Windows (PowerShell)**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3) Install dependencies

If you have a `requirements.txt` file:
```bash
pip install -r requirements.txt
```

If not, install Django directly:
```bash
pip install django
```

### 4) Configure environment variables

Create or update:

```bash
fuel_route/.env
```

Add any required environment keys used by your app/scripts (API keys, debug flags, etc.).

### 5) Run migrations

From the `fuel_route` directory:

```bash
cd fuel_route
python manage.py migrate
```

### 6) Start the development server

```bash
python manage.py runserver
```

Server should be available at:
- `http://127.0.0.1:8000/`

## Geocoding Scripts

The project includes geocoding utilities:

- `fuel_route/geocode_stations.py`
- `fuel_route/geocode_stations_fast.py`

Run them from the `fuel_route/` directory, for example:

```bash
python geocode_stations.py
python geocode_stations_fast.py
```

> Ensure any required API keys/environment variables are configured in `.env` before running.

## Project Commands

From `fuel_route/`:

```bash
python manage.py runserver      # Run dev server
python manage.py migrate        # Apply migrations
python manage.py makemigrations # Create migrations
python manage.py createsuperuser
python manage.py test           # Run tests
```

## API Endpoints

Endpoint definitions are expected to be in the `routes` app.  
If you expose routes through a root `urls.py`, document them here, for example:

- `GET /api/routes/...`
- `POST /api/routes/...`

_(Update this section with actual endpoint paths and request/response examples.)_

## Development Notes

- Keep secrets out of version control (`.env`, API keys, credentials)
- Prefer adding a `requirements.txt` for reproducible setup
- Avoid committing local artifacts (virtual envs, local DB) in collaborative workflows

## Contributing

1. Fork the repo
2. Create a feature branch
3. Commit your changes
4. Open a pull request

## License

No license is currently specified in this repository.  
Consider adding a `LICENSE` file (e.g., MIT, Apache-2.0) for clarity.
