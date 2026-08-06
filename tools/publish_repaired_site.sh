#!/usr/bin/env bash
set -euo pipefail

repo_root="${GITHUB_WORKSPACE:-$(pwd)}"
site_root="${RUNNER_TEMP:-/tmp}/llb-site"
evidence="${RUNNER_TEMP:-/tmp}/llb-repair-evidence"
repair_ref="origin/repair/full-case-catalogue-routing"

mkdir -p "$evidence"
cd "$repo_root"

echo "Fetching staged repair source"
git fetch --no-tags origin repair/full-case-catalogue-routing:refs/remotes/origin/repair/full-case-catalogue-routing

mapfile -t archive_parts < <(
  git ls-tree -r --name-only "$repair_ref" -- tools \
    | grep '^tools/site-repair-core\.tar\.xz\.b64\.part[0-9][0-9]$' \
    | sort
)
if (( ${#archive_parts[@]} < 13 )); then
  printf 'Only %s staged archive parts were found\n' "${#archive_parts[@]}" >&2
  exit 1
fi
printf '%s\n' "${archive_parts[@]}" | tee "$evidence/archive-parts.txt"

bundle_b64="${RUNNER_TEMP:-/tmp}/site-repair-core.tar.xz.b64"
bundle="${RUNNER_TEMP:-/tmp}/site-repair-core.tar.xz"
: > "$bundle_b64"
for part in "${archive_parts[@]}"; do
  git show "$repair_ref:$part" >> "$bundle_b64"
done
base64 --decode "$bundle_b64" > "$bundle"
sha256sum "$bundle" | tee "$evidence/repair-archive.sha256"
xz --test "$bundle"
tar -tJf "$bundle" | tee "$evidence/repair-archive-files.txt"
tar -xJf "$bundle" -C "$repo_root"

for required in \
  tools/build_site.py \
  tools/enrich_nodes.py \
  tools/build_cases.py \
  casebook/relationships.json \
  casebook/SOURCE-MANIFEST.sha256; do
  test -f "$required" || { echo "Missing restored source: $required" >&2; exit 1; }
done

python -m py_compile tools/build_site.py tools/enrich_nodes.py tools/build_cases.py
sha256sum --check casebook/SOURCE-MANIFEST.sha256 | tee "$evidence/source-manifest-check.txt"
find tools casebook -type d -name __pycache__ -prune -exec rm -rf {} +

rm -rf "$site_root"
export LLB_SITE_ROOT="$site_root"
echo "Generating graph and study pages"
python tools/build_site.py 2>&1 | tee "$evidence/build-site.log"
echo "Enriching every curriculum node"
python tools/enrich_nodes.py --root "$site_root" 2>&1 | tee "$evidence/enrich-nodes.log"
echo "Generating the case catalogue"
python tools/build_cases.py --root "$site_root" --catalogue casebook 2>&1 | tee "$evidence/build-cases.log"

node --check "$site_root/app.js"
node --check "$site_root/node.js"
node --check "$site_root/case.js"
node --check "$site_root/sw.js"

python tools/validate_repaired_site.py "$site_root" "$evidence/static-validation.json" \
  | tee "$evidence/static-validation.stdout.txt"

cat > "$evidence/local-routes.tsv" <<'EOF'
name	path
root	/
cases	/cases/
maneka	/cases/sc-1978-maneka-gandhi-v-union-of-india/
review	/cases/review/
offline	/offline.html
styles	/styles.css
case-css	/case.css
service-worker	/sw.js
EOF

python -m http.server 8765 --directory "$site_root" > "$evidence/http-server.log" 2>&1 &
server_pid=$!
cleanup() { kill "$server_pid" 2>/dev/null || true; }
trap cleanup EXIT
for _ in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8765/cases/ >/dev/null; then break; fi
  sleep 1
done

printf 'name\tcode\ttype\tbytes\tsha256\n' > "$evidence/local-curl.tsv"
while IFS=$'\t' read -r name path; do
  [[ "$name" == "name" ]] && continue
  body="$evidence/local-$name.body"
  metrics=$(curl -sS -o "$body" -w '%{http_code}\t%{content_type}\t%{size_download}' "http://127.0.0.1:8765$path")
  hash=$(sha256sum "$body" | awk '{print $1}')
  printf '%s\t%s\t%s\n' "$name" "$metrics" "$hash" >> "$evidence/local-curl.tsv"
done < "$evidence/local-routes.tsv"
cat "$evidence/local-curl.tsv"

chrome="$(command -v google-chrome-stable || command -v google-chrome || command -v chromium || command -v chromium-browser || true)"
test -n "$chrome" || { echo 'Chrome/Chromium is unavailable on the runner' >&2; exit 1; }
"$chrome" --version | tee "$evidence/chrome-version.txt"

for item in root cases maneka review; do
  case "$item" in
    root) path='/' ;;
    cases) path='/cases/' ;;
    maneka) path='/cases/sc-1978-maneka-gandhi-v-union-of-india/' ;;
    review) path='/cases/review/' ;;
  esac
  for spec in mobile:390,844 desktop:1440,1000; do
    label=${spec%%:*}
    size=${spec#*:}
    "$chrome" \
      --headless=new \
      --no-sandbox \
      --disable-dev-shm-usage \
      --hide-scrollbars \
      --force-device-scale-factor=1 \
      --window-size="$size" \
      --virtual-time-budget=5000 \
      --screenshot="$evidence/${label}-${item}.png" \
      "http://127.0.0.1:8765${path}" \
      > "$evidence/${label}-${item}.chrome.log" 2>&1
  done
done
file "$evidence"/*.png | tee "$evidence/screenshot-files.txt"
cleanup
trap - EXIT

rsync -a --delete \
  --exclude='.git/' \
  --exclude='.github/' \
  --exclude='tools/' \
  --exclude='casebook/' \
  "$site_root/" "$repo_root/"
find tools casebook -type d -name __pycache__ -prune -exec rm -rf {} +

git config user.name 'github-actions[bot]'
git config user.email '41898282+github-actions[bot]@users.noreply.github.com'
git add -A
if git diff --cached --quiet; then
  echo 'Generated output already matches the checkout.'
else
  git commit -m 'Build validated styled LL.B. case catalogue'
fi

generated_commit=$(git rev-parse HEAD)
printf '%s\n' "$generated_commit" | tee "$evidence/generated-commit.txt"
git status --short | tee "$evidence/git-status.txt"
git push --force origin HEAD:refs/heads/generated/site-repair-live

echo "Validated generated branch: generated/site-repair-live at $generated_commit"
