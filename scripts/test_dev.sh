#!/bin/bash

set -e
export MODE=testing

source .env

# Create a PostgreSQL container
echo 'Starting the test container...'
docker create --name test_postgres_ora_backend -v test_postgres_ora_backend_dbdata:/var/lib/postgresql/data -p 54321:5432 postgres:11 || true
docker create --name test_redis_ora_backend -e REDIS_PASSWORD=$CELERY_BROKER_PASSWORD -p 63791:6379 bitnami/redis:latest || true

# Start the test container
docker start test_postgres_ora_backend

# Clear all tables
echo "Setting up the test DB..."
docker exec -it test_postgres_ora_backend psql -U postgres -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public; GRANT ALL ON SCHEMA public TO postgres; GRANT ALL ON SCHEMA public TO public;"
docker start -a test_redis_ora_backend || docker exec -it test_redis_ora_backend redis-cli -a $CELERY_BROKER_PASSWORD flushall || docker exec -it test_redis_ora_backend redis-server &

# Run the actual tests
pipenv run pytest --loop uvloop --ignore=ora_backend/tests/test_chat.py
# pipenv run pytest -s --loop uvloop ora_backend/tests/test_chat.py
# pipenv run pytest --loop uvloop ora_backend/tests/utils/test_query.py::test_get_flagged_chats_of_online_visitors
# pipenv run pytest --loop uvloop ora_backend/tests/test_user.py::test_get_one_user

# Stop the container after running
echo 'Shutting down the test container...'
docker stop test_postgres_ora_backend
