#!/usr/bin/env bash
set -euo pipefail

repo_root="${GITHUB_WORKSPACE:-$(pwd)}"
site_root="${RUNNER_TEMP:-/tmp}/llb-site"
evidence="${RUNNER_TEMP:-/tmp}/llb-repair-evidence"
repair_ref="origin/repair/full-case-catalogue-routing"
mkdir -p "$evidence"
cd "$repo_root"

echo "Fetching staged case-catalogue source"
git fetch --no-tags origin repair/full-case-catalogue-routing:refs/remotes/origin/repair/full-case-catalogue-routing
mapfile -t parts < <(git ls-tree -r --name-only "$repair_ref" -- tools | grep '^tools/site-repair-core\.tar\.xz\.b64\.part[0-9][0-9]$' | sort)
(( ${#parts[@]} >= 13 )) || { echo "Only ${#parts[@]} archive parts found" >&2; exit 1; }
printf '%s\n' "${parts[@]}" | tee "$evidence/archive-parts.txt"
b64="${RUNNER_TEMP:-/tmp}/site-repair-core.tar.xz.b64"
bundle="${RUNNER_TEMP:-/tmp}/site-repair-core.tar.xz"
: > "$b64"
for part in "${parts[@]}"; do git show "$repair_ref:$part" >> "$b64"; done
base64 --decode "$b64" > "$bundle"
sha256sum "$bundle" | tee "$evidence/repair-archive.sha256"
xz --test "$bundle"
tar -xJf "$bundle" -C "$repo_root"

for required in tools/build_site.py tools/enrich_nodes.py tools/build_cases.py casebook/relationships.json casebook/SOURCE-MANIFEST.sha256; do
  test -f "$required" || { echo "Missing restored source: $required" >&2; exit 1; }
done
python -m py_compile tools/build_site.py tools/enrich_nodes.py tools/build_cases.py
sha256sum --check casebook/SOURCE-MANIFEST.sha256 | tee "$evidence/source-manifest-check.txt"

rm -rf "$site_root"
export LLB_SITE_ROOT="$site_root"
python tools/build_site.py 2>&1 | tee "$evidence/build-site.log"
python tools/enrich_nodes.py --root "$site_root" 2>&1 | tee "$evidence/enrich-nodes.log"
python tools/build_cases.py --root "$site_root" --catalogue casebook 2>&1 | tee "$evidence/build-cases.log"

# Apply the route-safe presentation layer after generation.
cp tools/repair-assets/404.html "$site_root/404.html"
cp tools/repair-assets/offline.html "$site_root/offline.html"
cp tools/repair-assets/sw.js "$site_root/sw.js"
printf '%s\n' 'LLB_STATIC_REPAIR_20260807_V3' > "$site_root/deploy-marker.txt"
cat >> "$site_root/case.css" <<'CSS'

/* Mobile header guard: retain identity and primary catalogue routes without clipping. */
@media(max-width:520px){.case-header .header-row{padding:.55rem .75rem}.case-header nav a:nth-child(n+3){display:none}.case-header .brand strong{max-width:145px;line-height:1.05}}
CSS
python - <<'PY'
import os
from pathlib import Path
root=Path(os.environ['LLB_SITE_ROOT'])
index=root/'cases/index.html'
s=index.read_text(encoding='utf-8')
s=s.replace('<a href="../sources/">Course sources</a>','<a href="https://lawfaculty.du.ac.in/Students/LL.B.-Course-Materials" target="_blank" rel="noopener">DU course materials</a>')
index.write_text(s,encoding='utf-8')
case_js=root/'case.js'
s=case_js.read_text(encoding='utf-8')
pos=s.rfind('})();')
if pos < 0: raise SystemExit('case.js IIFE close missing')
registration="if('serviceWorker' in navigator&&location.protocol.startsWith('http'))navigator.serviceWorker.register('/llb/sw.js').catch(()=>{});\n"
case_js.write_text(s[:pos]+registration+s[pos:],encoding='utf-8')
PY

node --check "$site_root/app.js"
node --check "$site_root/node.js"
node --check "$site_root/case.js"
node --check "$site_root/sw.js"
python tools/validate_repaired_site.py "$site_root" "$evidence/static-validation.json" | tee "$evidence/static-validation.stdout.txt"

# Real local HTTP and system-Chrome renders before publication.
python -m http.server 8765 --directory "$site_root" > "$evidence/http-server.log" 2>&1 &
server_pid=$!
cleanup(){ kill "$server_pid" 2>/dev/null || true; }
trap cleanup EXIT
for _ in $(seq 1 30); do curl -fsS http://127.0.0.1:8765/cases/ >/dev/null && break; sleep 1; done
cat > "$evidence/local-routes.tsv" <<'EOF'
root	/
cases	/cases/
maneka	/cases/sc-1978-maneka-gandhi-v-union-of-india/
review	/cases/review/
trail	/cases/trails/liberty-due-process-and-privacy/
casebook	/subjects/lb-401/cases/
node	/nodes/lb-401.m03.s16/
offline	/offline.html
styles	/styles.css
case-css	/case.css
service-worker	/sw.js
EOF
printf 'name\tcode\ttype\tbytes\tsha256\n' > "$evidence/local-curl.tsv"
while IFS=$'\t' read -r name path; do
  body="$evidence/local-$name.body"
  metrics=$(curl -sS -o "$body" -w '%{http_code}\t%{content_type}\t%{size_download}' "http://127.0.0.1:8765$path")
  hash=$(sha256sum "$body" | awk '{print $1}')
  printf '%s\t%s\t%s\n' "$name" "$metrics" "$hash" >> "$evidence/local-curl.tsv"
done < "$evidence/local-routes.tsv"
cat "$evidence/local-curl.tsv"
chrome="$(command -v google-chrome-stable || command -v google-chrome || command -v chromium || command -v chromium-browser || true)"
test -n "$chrome" || { echo 'Chrome unavailable' >&2; exit 1; }
"$chrome" --version | tee "$evidence/chrome-version.txt"
for item in root cases maneka review trail casebook node; do
  case "$item" in
    root) path='/' ;;
    cases) path='/cases/' ;;
    maneka) path='/cases/sc-1978-maneka-gandhi-v-union-of-india/' ;;
    review) path='/cases/review/' ;;
    trail) path='/cases/trails/liberty-due-process-and-privacy/' ;;
    casebook) path='/subjects/lb-401/cases/' ;;
    node) path='/nodes/lb-401.m03.s16/' ;;
  esac
  for spec in mobile:390,844 desktop:1440,1000; do
    label=${spec%%:*}; size=${spec#*:}
    "$chrome" --headless=new --no-sandbox --disable-dev-shm-usage --hide-scrollbars --force-device-scale-factor=1 \
      --window-size="$size" --virtual-time-budget=7000 --screenshot="$evidence/${label}-${item}.png" \
      "http://127.0.0.1:8765${path}" > "$evidence/${label}-${item}.chrome.log" 2>&1
  done
done
file "$evidence"/*.png | tee "$evidence/screenshot-files.txt"
cleanup; trap - EXIT

# Replace the deployed root, preserve build machinery, and publish to main.
rsync -a --delete --exclude='.git/' --exclude='.github/' --exclude='tools/' --exclude='casebook/' "$site_root/" "$repo_root/"
rm -rf casebook
git restore --worktree -- tools
git clean -fd -- tools casebook
find tools -type d -name __pycache__ -prune -exec rm -rf {} +
git config user.name 'github-actions[bot]'
git config user.email '41898282+github-actions[bot]@users.noreply.github.com'
git add -A
if ! git diff --cached --quiet; then git commit -m 'Deploy styled LL.B. case catalogue and repair nested routes'; fi
generated_commit=$(git rev-parse HEAD)
echo "$generated_commit" | tee "$evidence/generated-commit.txt"
git status --short | tee "$evidence/git-status.txt"
git push origin HEAD:main
echo "Published repaired site commit $generated_commit to main"
