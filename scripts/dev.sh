#!/bin/bash

set -e
export MODE=development

source .env

# Create a PostgreSQL container
docker create --name dev_postgres_ora_backend -v dev_postgres_ora_backend_dbdata:/var/lib/postgresql/data -p 54320:5432 postgres:11 || true
docker create --name dev_redis_ora_backend -e REDIS_PASSWORD=$CELERY_BROKER_PASSWORD -p 6379:6379 bitnami/redis:latest || true


# Start the containers
# docker run --name my_postgres -v my_dbdata:/var/lib/postgresql/data -p 54320:5432 postgres:11 || docker start -a my_postgres
docker start -a dev_postgres_ora_backend &
docker start -a dev_redis_ora_backend || docker exec -it dev_redis_ora_backend redis-cli -a $CELERY_BROKER_PASSWORD flushall || docker exec -it dev_redis_ora_backend redis-server &

# docker exec -it dev_redis_ora_backend redis-server

# Also, run the Python app
pipenv run python app.py &
# pipenv run hypercorn --bind 0.0.0.0:8000 --keep-alive 10 --worker-class uvloop --workers 3 app:app &
# pipenv run hypercorn --bind 0.0.0.0:8080 --keep-alive 10 --worker-class uvloop --workers 1 app_socketio:app &

pipenv run python app_socketio.py &
# pipenv run hypercorn --keep-alive 10 --workers 3 --bind 127.0.0.1:8000 app:app

# Allow both the Postgres container and Python app
# to run in parallel
wait
