#!/bin/bash

set -e
export MODE=production

celery -A ora_backend.worker.tasks worker --loglevel=info
