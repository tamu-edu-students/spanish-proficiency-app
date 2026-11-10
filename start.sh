#!/bin/sh
# Container entrypoint (Cloud Run). Every deploy:
#  1. applies pending migrations — including the PromptPool flushes — before serving;
#  2. tops the prompt pool up in the background, so startup isn't held for ~150 Gemini
#     calls. prefill only adds what's missing, so on an already-full pool it's quick.
# ponytail: each new instance runs this; concurrent migrate on scale-out is usually a
# no-op but move it to a Cloud Run job if migrations ever get slow or conflict.
set -e

python manage.py migrate --noinput
python manage.py prefill_prompts &

exec daphne -b 0.0.0.0 -p "${PORT:-8080}" backend.asgi:application
