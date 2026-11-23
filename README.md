<div align="center">

<img src="./screenshots/illustration.png" alt="Job Interview" width="300" height="356.5">

# Django Job Portal

</div>

## Django Job Portal

#### An open source online job portal.

<p align="center">
    <img alt="forks" src="https://img.shields.io/github/forks/manjurulhoque/django-job-portal?label=Forks&style=social"/>
    <img alt="stars" src="https://img.shields.io/github/stars/manjurulhoque/django-job-portal?style=social"/>
    <img alt="watchers" src="https://img.shields.io/github/watchers/manjurulhoque/django-job-portal?style=social"/>
    <img alt="github Actions" src="https://github.com/manjurulhoque/django-job-portal/workflows/job-portal/badge.svg"/>
</p>

Live: [Demo](http://djp.manjurulhoque.com/en/)

Used Tech Stack

1. FastAPI (Starlette, Jinja templates)
2. SQLAlchemy 2.0 with Alembic migrations
3. Sqlite

### Screenshots

## Home page
<img src="screenshots/home.png" height="800">

## Companies page
<img src="screenshots/companies.png">

## Resume template page
<img src="screenshots/six.png" height="800">
<img src="screenshots/seven.png" height="800">

## Add new position as employer
<img src="screenshots/post.png" width="800" alt="form">

## Job details
<img src="screenshots/details.png" alt="details">

## Swagger API
<img src="screenshots/four.png" height="800">

<a name="local-venv"></a>
### Local environment

#### Install

1. Create a virtual environment

    `virtualenv venv`

    Or

    `python3.11 -m venv venv`

2. Activate it

    `source venv/bin/activate`

3. Clone the repository and install the packages in the virtual env:

    `pip install -r requirements.txt`

4. Add `.env` file.

    `cp .env.dev.sample .env`

5. Add Github client ID and client secret in the `.env` file

#### Run

1. Choose the database (optional; it defaults to the `db.sqlite3` file in the project):

    `export DATABASE_URL=sqlite:///db.sqlite3`

2. Create or update the schema:

    `alembic upgrade head`

3. Run the server:

    `uvicorn app.main:app --reload`

   In production the same application is served behind gunicorn:

    `gunicorn app.main:app -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000`

4. The interactive API documentation is served at `/api/docs`.

#### Run test:
``pytest -q``

#### To add a migration:
``alembic revision -m "what changed"``

![Analytics](https://repobeats.axiom.co/api/embed/2ed66773eb8b3acef70bc808ddc6701253f2fc09.svg "Repobeats analytics image")

Show your support by 🌟 the project!!

# Testing

The suite under `tests/` runs with `pytest`. It drives the application through Starlette's
test client against a throwaway SQLite database that the project's own Alembic revisions
build, so the tests exercise the same schema the deployment has.

```
pytest -q
pytest -q tests/test_api_views.py
```
