#!/bin/bash

set -e
export MODE=development

# Create a PostgreSQL container
docker create --name dev_postgres_ora_backend -v dev_postgres_ora_backend_dbdata:/var/lib/postgresql/data -p 54320:5432 postgres:11 || true

# Start a Postgres container
# docker run --name my_postgres -v my_dbdata:/var/lib/postgresql/data -p 54320:5432 postgres:11 || docker start -a my_postgres
docker start -a dev_postgres_ora_backend &

# Also, run the Python app
pipenv run python app.py &
# pipenv run python app_socketio.py &
pipenv run python ora_backend/socketio_apps/app_socketio_1.py &
pipenv run python ora_backend/socketio_apps/app_socketio_2.py &
pipenv run python ora_backend/socketio_apps/app_socketio_3.py &

# pipenv run hypercorn --keep-alive 10 --workers 3 --bind 127.0.0.1:8000 app:app

# Allow both the Postgres container and Python app
# to run in parallel
wait
