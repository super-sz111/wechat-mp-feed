#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${WECHAT_DOWNLOAD_API_REPO_URL:-https://github.com/tmwgsicp/wechat-download-api.git}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_INSTALL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)/../wechat-download-api"
INSTALL_DIR="${WECHAT_DOWNLOAD_API_DIR:-$DEFAULT_INSTALL_DIR}"
BASE_URL="${WECHAT_DOWNLOAD_API_BASE_URL:-http://127.0.0.1:5000}"
OPEN_LOGIN=1

for arg in "$@"; do
  case "$arg" in
    --no-open)
      OPEN_LOGIN=0
      ;;
    --dir=*)
      INSTALL_DIR="${arg#--dir=}"
      ;;
    --base-url=*)
      BASE_URL="${arg#--base-url=}"
      ;;
    *)
      echo "Unknown argument: $arg" >&2
      exit 2
      ;;
  esac
done

if ! command -v git >/dev/null 2>&1; then
  echo "git is required." >&2
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required." >&2
  exit 1
fi

if [ ! -d "$INSTALL_DIR/.git" ]; then
  mkdir -p "$(dirname "$INSTALL_DIR")"
  git clone "$REPO_URL" "$INSTALL_DIR"
fi

cd "$INSTALL_DIR"

if [ ! -f .env ]; then
  if [ -f env.example ]; then
    cp env.example .env
  elif [ -f .env.example ]; then
    cp .env.example .env
  else
    touch .env
  fi
fi

HOST_PORT="$(python3 - "$BASE_URL" <<'PY'
from urllib.parse import urlparse
import sys

parsed = urlparse(sys.argv[1])
print(parsed.port or (443 if parsed.scheme == "https" else 80))
PY
)"

while lsof -nP -iTCP:"$HOST_PORT" -sTCP:LISTEN >/dev/null 2>&1; do
  HOST_PORT="$((HOST_PORT + 1))"
done

BASE_URL="$(python3 - "$BASE_URL" "$HOST_PORT" <<'PY'
from urllib.parse import urlparse, urlunparse
import sys

parsed = urlparse(sys.argv[1])
port = sys.argv[2]
netloc = parsed.hostname or "127.0.0.1"
if parsed.username:
    auth = parsed.username
    if parsed.password:
        auth += f":{parsed.password}"
    netloc = f"{auth}@{netloc}"
print(urlunparse((parsed.scheme or "http", f"{netloc}:{port}", "", "", "", "")))
PY
)"

python3 - "$BASE_URL" <<'PY'
from pathlib import Path
import sys

path = Path(".env")
base_url = sys.argv[1]
lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
seen = False
for index, line in enumerate(lines):
    if line.startswith("SITE_URL="):
        lines[index] = f"SITE_URL={base_url}"
        seen = True
if not seen:
    lines.append(f"SITE_URL={base_url}")
path.write_text("\n".join(lines) + "\n", encoding="utf-8")
PY

python3 - "$HOST_PORT" <<'PY'
from pathlib import Path
import re
import sys

path = Path("docker-compose.yml")
text = path.read_text(encoding="utf-8")
replacement = f'- "127.0.0.1:{sys.argv[1]}:5000"'
text = re.sub(r'-\s*["\']?(?:127\.0\.0\.1:)?\d+:5000["\']?', replacement, text, count=1)
path.write_text(text, encoding="utf-8")
PY

docker compose up -d

LOGIN_URL="${BASE_URL%/}/login.html"
echo "wechat-download-api is starting at: $BASE_URL"
echo "Open this URL and scan the WeChat QR code: $LOGIN_URL"

if [ "$OPEN_LOGIN" -eq 1 ] && command -v open >/dev/null 2>&1; then
  open "$LOGIN_URL"
fi
