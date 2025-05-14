# FastApi-Server

A FastAPI project with async support, multi-core optimization, and performance testing.

## Setup
1. Configure `.env` with your database credentials.
2. Install dependencies: `pip install -r requirements.txt`.
3. Run locally: `gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app`.
4. Or use Docker: `docker build -t myapp . && docker run -p 8000:8000 myapp`.
5. Run tests: `pytest tests/`.

## Features
- Async database operations with PostgreSQL.
- Multi-core support via Gunicorn/Uvicorn workers.
- Performance measurement in tests.