#!/usr/bin/env bash
set -euo pipefail

repo_root="${GITHUB_WORKSPACE:-$(pwd)}"
site_root="${RUNNER_TEMP:-/tmp}/llb-site-v4"
source_root="${RUNNER_TEMP:-/tmp}/llb-case-source-v4"
evidence="${RUNNER_TEMP:-/tmp}/llb-site-v4-evidence"
archive="$repo_root/tools/case-publisher.tar.xz"
archive_sha="0f5796be874452120bd31af08263bb9c0cd755e31c934fd3958baf4d4f5ad692"

mkdir -p "$evidence"
cd "$repo_root"

printf '%s  %s\n' "$archive_sha" "$archive" | sha256sum --check - | tee "$evidence/archive-check.txt"
xz --test "$archive"
rm -rf "$source_root" "$site_root"
mkdir -p "$source_root" "$site_root"
tar -xJf "$archive" -C "$source_root"
publisher="$source_root/llb-case-catalogue-publisher"
test -d "$publisher/casebook"
test -f "$publisher/tools/enrich_nodes.py"
test -f "$publisher/tools/build_cases.py"
(
  cd "$publisher"
  sha256sum --check SOURCE-MANIFEST.sha256
) | tee "$evidence/source-manifest-check.txt"

rm -rf casebook
cp -a "$publisher/casebook" casebook
cp "$publisher/tools/enrich_nodes.py" tools/enrich_nodes.py
cp "$publisher/tools/build_cases.py" tools/build_cases.py
find tools casebook -type d -name __pycache__ -prune -exec rm -rf {} +

python -m py_compile tools/build_site.py tools/enrich_nodes.py tools/build_cases.py
export LLB_SITE_ROOT="$site_root"
python tools/build_site.py 2>&1 | tee "$evidence/build-site.log"
python tools/enrich_nodes.py --root "$site_root" 2>&1 | tee "$evidence/enrich-nodes.log"
python tools/build_cases.py --root "$site_root" --catalogue casebook 2>&1 | tee "$evidence/build-cases.log"

# Replace route-sensitive fallbacks with self-contained, repository-scope-safe versions.
cp tools/repair-assets/404.html "$site_root/404.html"
cp tools/repair-assets/offline.html "$site_root/offline.html"
cp tools/repair-assets/sw.js "$site_root/sw.js"
printf '%s\n' 'LLB_STATIC_REPAIR_20260807_V4' > "$site_root/deploy-marker.txt"

python - "$site_root" <<'PY'
from pathlib import Path
import sys

root = Path(sys.argv[1])
case_js = root / "case.js"
text = case_js.read_text(encoding="utf-8")
registration = "\nif('serviceWorker' in navigator&&location.protocol.startsWith('http'))navigator.serviceWorker.register('/llb/sw.js').catch(()=>{});\n"
if "/llb/sw.js" not in text:
    case_js.write_text(text.rstrip() + registration, encoding="utf-8")

case_css = root / "case.css"
css = case_css.read_text(encoding="utf-8")
guard = "\n/* Mobile header guard: keep identity and core routes readable without horizontal clipping. */\n@media(max-width:520px){.case-header .header-row{padding:.55rem .75rem}.case-header nav a:nth-child(n+3){display:none}.case-header .brand strong{max-width:145px;line-height:1.05}}\n"
if "Mobile header guard" not in css:
    case_css.write_text(css.rstrip() + "\n" + guard, encoding="utf-8")

catalogue = root / "cases" / "index.html"
page = catalogue.read_text(encoding="utf-8")
page = page.replace(
    '<a href="../sources/">Course sources</a>',
    '<a href="https://lawfaculty.du.ac.in/Students/LL.B.-Course-Materials" target="_blank" rel="noopener">DU course materials</a>',
)
catalogue.write_text(page, encoding="utf-8")
PY

node --check "$site_root/app.js"
node --check "$site_root/node.js"
node --check "$site_root/case.js"
node --check "$site_root/sw.js"
python tools/validate_repaired_site.py "$site_root" "$evidence/static-validation.json" | tee "$evidence/static-validation.stdout.txt"

python -m http.server 8765 --directory "$site_root" > "$evidence/http-server.log" 2>&1 &
server_pid=$!
cleanup() { kill "$server_pid" 2>/dev/null || true; }
trap cleanup EXIT
for _ in $(seq 1 30); do
  curl -fsS http://127.0.0.1:8765/cases/ >/dev/null && break
  sleep 1
done
printf 'name\tcode\ttype\tbytes\n' > "$evidence/local-curl.tsv"
while IFS=$'\t' read -r name path; do
  metrics=$(curl -sS -o "$evidence/$name.body" -w '%{http_code}\t%{content_type}\t%{size_download}' "http://127.0.0.1:8765$path")
  printf '%s\t%s\n' "$name" "$metrics" >> "$evidence/local-curl.tsv"
done <<'ROUTES'
root	/
cases	/cases/
maneka	/cases/sc-1978-maneka-gandhi-v-union-of-india/
review	/cases/review/
trail	/cases/trails/liberty-due-process-and-privacy/
node	/nodes/lb-101.m01.t01/
styles	/styles.css
case-css	/case.css
case-js	/case.js
worker	/sw.js
offline	/offline.html
ROUTES
cat "$evidence/local-curl.tsv"
awk -F '\t' 'NR>1 && $2 != 200 { bad=1 } END { exit bad }' "$evidence/local-curl.tsv"
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
  echo 'Generated root already matches the validated build.'
else
  git commit -m 'Publish complete styled LL.B. case catalogue and repair nested routes'
  git push origin HEAD:main
fi
git rev-parse HEAD | tee "$evidence/generated-commit.txt"
git status --short | tee "$evidence/git-status.txt"
