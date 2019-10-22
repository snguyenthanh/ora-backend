#!/bin/bash

set -e
export MODE=development
export PYTHONPATH=.

echo "INFO: Clearing all tables..."
docker exec -it dev_postgres_ora_backend psql -U postgres -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public; GRANT ALL ON SCHEMA public TO postgres; GRANT ALL ON SCHEMA public TO public;"

echo "INFO: Adding test rows..."
pipenv run python ora_backend/tests/setup_dev_db.py
