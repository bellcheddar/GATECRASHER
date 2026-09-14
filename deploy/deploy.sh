#!/usr/bin/env bash
# Push GATECRASHER's static bundle from the Mac to the droplet.
# Run from the repo root:  bash deploy/deploy.sh
#
# The whole app is static, so this is one rsync: no service to restart, no venv to install,
# no database to avoid clobbering. BUILD_SPEC ground rule 2 is what makes that true.
#
# Reads DROPLET_SSH / DROPLET_PATH from .env (see .env.example).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Config lives beside this script, next to .env.example, and .gitignore protects it there.
# The repo root is still read as a fallback for anyone who put it there first.
for envfile in deploy/.env .env; do
  if [[ -f "$envfile" ]]; then set -a; source "$envfile"; set +a; break; fi
done
DROPLET_SSH="${DROPLET_SSH:-}"
DROPLET_PATH="${DROPLET_PATH:-/var/www/gatecrasher}"
SSH_KEY="${SSH_KEY:-}"

if [[ -z "$DROPLET_SSH" ]]; then
  echo "DROPLET_SSH is not set. Copy .env.example to .env and fill it in."; exit 1
fi

# ---------------------------------------------------------------- validate before shipping
# Never deploy a bundle that does not validate. The gate is cheap and the alternative is
# publishing a page whose numbers have no provenance.
echo "==> Validating every bundle"
PY="${GATECRASHER_PY:-$HOME/.venvs/gatecrasher/bin/python}"
if [[ -x "$PY" ]]; then
  (cd pipeline && "$PY" -m gcrash.cli validate)
else
  echo "    no pipeline environment at $PY, skipping (CI validates on every push)"
fi

# ------------------------------------------------------------------- stamp the asset URLs
# nginx serves css/js/wasm as immutable, so an unstamped URL would pin the old file forever.
# Each reference gets ?v=<mtime of the file>, which changes only when the file does.
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
cp -R web/ "$STAGE/web"

echo "==> Stamping asset URLs with their modification times"
python3 - "$STAGE/web" <<'PY'
import pathlib, re, sys

root = pathlib.Path(sys.argv[1])
index = root / "index.html"
html = index.read_text()

def stamp(match):
    attr, path = match.group(1), match.group(2)
    target = root / path
    if not target.is_file():
        return match.group(0)
    return f'{attr}="{path}?v={int(target.stat().st_mtime)}"'

html = re.sub(r'(href|src)="((?:css|js)/[^"?]+)"', stamp, html)
index.write_text(html)
print(f"    stamped {len(re.findall(r'\\?v=', html))} references")
PY

echo "==> Syncing to ${DROPLET_SSH}:${DROPLET_PATH}"
SSH_OPTS=()
[[ -n "$SSH_KEY" ]] && SSH_OPTS=(-e "ssh -i ${SSH_KEY/#\~/$HOME}")

# --delete is safe here and nowhere else in this portfolio: the destination holds only this
# static bundle, with no server-side state, no uploads and no database. Everything served
# is regenerated from the repo by gc bundle.
# ${arr[@]+"${arr[@]}"} expands to nothing when empty without tripping `set -u` on bash 3.2.
rsync -az --delete ${SSH_OPTS[@]+"${SSH_OPTS[@]}"} \
  "$STAGE/web/" "${DROPLET_SSH}:${DROPLET_PATH}/"

echo "==> Deployed. Verifying the live page"
SERVER_NAME="${SERVER_NAME:-gatecrasher.mdeller.com}"
sleep 1
code=$(curl -s -o /dev/null -w '%{http_code}' "https://${SERVER_NAME}/")
data=$(curl -s -o /dev/null -w '%{http_code}' "https://${SERVER_NAME}/data/index.json")
echo "    https://${SERVER_NAME}/                 ${code}"
echo "    https://${SERVER_NAME}/data/index.json  ${data}"
[[ "$code" == "200" && "$data" == "200" ]] || { echo "    live check FAILED"; exit 1; }

# A status code is not enough, and this is not hypothetical: a stray `types` block in the
# vhost once made nginx serve every asset as application/octet-stream. Browsers refuse
# stylesheets and ES modules with that type, so the site was blank furniture while every
# file returned 200 and this script happily printed "Live". Check what the bytes claim to be.
echo "==> Verifying content types"
ct_fail=0
check_type() {
  local path="$1" want="$2"
  local got
  got=$(curl -s -D- -o /dev/null "https://${SERVER_NAME}/${path}" \
        | tr -d '\r' | awk 'tolower($1)=="content-type:"{print $2}')
  printf '    %-32s %s\n' "$path" "${got:-none}"
  case "$got" in *"$want"*) ;; *) echo "        expected $want"; ct_fail=1 ;; esac
}
check_type "css/tokens.css"                 "text/css"
check_type "js/app.js"                      "javascript"
check_type "data/index.json"                "application/json"
check_type "icon.svg"                       "image/svg+xml"
check_type "js/vendor/RDKit_minimal.wasm"   "application/wasm"
[[ $ct_fail -eq 0 ]] || { echo "    content types are wrong: the page will not render"; exit 1; }

echo "==> Live: https://${SERVER_NAME}"
echo "    Run the browser check against production to be sure:"
echo "    python3 tools/browser_check.py --base https://${SERVER_NAME}"
