#!/bin/bash
# seed-camera.sh
# Runs once on first DB startup, right after schema.sql.
# Reads RTSP_* from the environment (injected by docker-compose) and inserts
# the seed camera row with a properly URL-encoded password.
#
# Files in /docker-entrypoint-initdb.d/ ending in .sh are executed by the
# Postgres entrypoint — they can read env vars, unlike raw .sql files.

set -euo pipefail

: "${RTSP_USER:?RTSP_USER must be set in .env}"
: "${RTSP_PASSWORD:?RTSP_PASSWORD must be set in .env}"
: "${RTSP_HOST:?RTSP_HOST must be set in .env}"
: "${RTSP_PORT:?RTSP_PORT must be set in .env}"
: "${RTSP_PATH:?RTSP_PATH must be set in .env}"

# URL-encode the password so special chars (@ & % * ! etc.) don't break the URL.
# Pure bash — the postgres image doesn't ship python3.
urlencode() {
  local s="$1" out="" c
  local LC_ALL=C
  for (( i=0; i<${#s}; i++ )); do
    c="${s:i:1}"
    case "$c" in
      [a-zA-Z0-9.~_-]) out+="$c" ;;
      *) printf -v out '%s%%%02X' "$out" "'$c" ;;
    esac
  done
  printf '%s' "$out"
}
RTSP_PASSWORD_ENC=$(urlencode "$RTSP_PASSWORD")

RTSP_URL="rtsp://${RTSP_USER}:${RTSP_PASSWORD_ENC}@${RTSP_HOST}:${RTSP_PORT}/${RTSP_PATH}"

psql \
  --username "$POSTGRES_USER" \
  --dbname   "$POSTGRES_DB" \
  --variable "rtsp_url=$RTSP_URL" \
  --set ON_ERROR_STOP=on <<'SQL'
INSERT INTO cameras (name, location, rtsp_url) VALUES
    ('Reolink Test',
     'Home — development camera',
     :'rtsp_url');
SQL
