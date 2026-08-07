#!/usr/bin/env bash
set -euo pipefail

repo_root="${GITHUB_WORKSPACE:-$(pwd)}"
work="${RUNNER_TEMP:-/tmp}/llb-case-v5"
source_root="$work/source"
evidence="${RUNNER_TEMP:-/tmp}/llb-case-v5-evidence"
archive="$work/case-lite-publisher.tar.xz"
expected_archive_sha="d24daca4cb1f29bce580eac2fbc3f295fc97188790a85c8edf5fbb9b6acaa803"

rm -rf "$work" "$evidence"
mkdir -p "$source_root" "$evidence"
cd "$repo_root"

cat tools/case-lite-publisher.tar.xz.b64.part{00..10} | base64 --decode > "$archive"
printf '%s  %s\n' "$expected_archive_sha" "$archive" | sha256sum --check - | tee "$evidence/archive-check.txt"
xz --test "$archive"
tar -xJf "$archive" -C "$source_root"

for required in build_case_lite.py case.css case.js case-lite.json; do
  test -s "$source_root/$required"
done
python -m py_compile "$source_root/build_case_lite.py"
node --check "$source_root/case.js"

python "$source_root/build_case_lite.py" \
  --root "$repo_root" \
  --bundle "$source_root/case-lite.json" \
  --assets "$source_root" \
  2>&1 | tee "$evidence/generator.log"

cat tools/case-detail-compat.css >> case.css
node --check case.js
node --check sw.js

python - "$repo_root" "$evidence/static-validation.json" <<'PY'
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

root = Path(sys.argv[1]).resolve()
out = Path(sys.argv[2])
coverage = json.loads((root / "data/case-coverage-report.json").read_text(encoding="utf-8"))
stats = coverage.get("stats", coverage)
expected = {
    "cases": 254,
    "nodeEdges": 665,
    "mappedNodes": 548,
    "trails": 27,
    "subjectsCovered": 45,
}
for key, value in expected.items():
    actual = stats.get(key)
    assert actual == value, (key, actual, value)

required = [
    "cases/index.html",
    "cases/sc-1978-maneka-gandhi-v-union-of-india/index.html",
    "cases/review/index.html",
    "cases/method/index.html",
    "cases/compare/index.html",
    "cases/trails/index.html",
    "cases/trails/liberty-due-process-and-privacy/index.html",
    "case.css",
    "case.js",
    "sw.js",
    "offline.html",
    "404.html",
    "deploy-marker.txt",
    "data/cases-index.json",
    "data/cases-full.json",
    "data/case-node-edges.json",
    "data/case-trails.json",
    "data/case-coverage-report.json",
]
missing = [path for path in required if not (root / path).is_file()]
assert not missing, missing
assert (root / "deploy-marker.txt").read_text(encoding="utf-8").strip() == "LLB_CASE_LITE_V5"

subject_casebooks = sorted(root.glob("subjects/*/cases/index.html"))
node_pages = sorted(root.glob("nodes/*/index.html"))
assert len(subject_casebooks) == stats["subjectsCovered"], (
    "subjectCasebooks", len(subject_casebooks), stats["subjectsCovered"]
)
assert len(node_pages) >= 4337, ("nodePages", len(node_pages))
assert "case-lite markup compatibility" in (root / "case.css").read_text(encoding="utf-8")

html_files = sorted(root.rglob("*.html"))
assert len(html_files) >= 4670, len(html_files)
id_re = re.compile(r"\bid=[\"']([^\"']+)[\"']", re.I)
attr_re = re.compile(r"\b(?:href|src)=[\"']([^\"']+)[\"']", re.I)
broken: list[tuple[str, str]] = []
missing_viewport: list[str] = []
missing_style: list[str] = []
duplicate_ids: list[str] = []

for page in html_files:
    text = page.read_text(encoding="utf-8")
    rel_page = str(page.relative_to(root))
    if '<meta name="viewport"' not in text and "<meta name='viewport'" not in text:
        missing_viewport.append(rel_page)
    if "stylesheet" not in text and "<style" not in text:
        missing_style.append(rel_page)
    ids = id_re.findall(text)
    if len(ids) != len(set(ids)):
        duplicate_ids.append(rel_page)
    for raw in attr_re.findall(text):
        ref = html.unescape(raw).strip()
        if (
            not ref
            or "${" in ref
            or ref.startswith(("#", "http:", "https:", "//", "mailto:", "tel:", "javascript:", "data:"))
        ):
            continue
        path = unquote(urlsplit(ref).path)
        if not path:
            continue
        if path.startswith("/llb/"):
            target = root / path.removeprefix("/llb/")
        elif path == "/llb":
            target = root / "index.html"
        elif path.startswith("/"):
            continue
        else:
            target = (page.parent / path).resolve()
            try:
                target.relative_to(root)
            except ValueError:
                continue
        if path.endswith("/"):
            target = target / "index.html"
        elif target.is_dir():
            target = target / "index.html"
        if not target.exists():
            broken.append((rel_page, ref))

assert not missing_viewport, missing_viewport[:20]
assert not missing_style, missing_style[:20]
assert not duplicate_ids, duplicate_ids[:20]
assert not broken, broken[:30]

report = {
    "valid": True,
    "htmlPages": len(html_files),
    "cases": stats["cases"],
    "nodeEdges": stats["nodeEdges"],
    "mappedNodes": stats["mappedNodes"],
    "trails": stats["trails"],
    "subjectsCovered": stats["subjectsCovered"],
    "brokenLinks": len(broken),
    "missingViewport": len(missing_viewport),
    "missingStyle": len(missing_style),
    "duplicateIds": len(duplicate_ids),
}
out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report, indent=2))
PY

http_root="$work/http-root"
mkdir -p "$http_root"
ln -s "$repo_root" "$http_root/llb"
python -m http.server 8765 --directory "$http_root" > "$evidence/http-server.log" 2>&1 &
server_pid=$!
cleanup() { kill "$server_pid" 2>/dev/null || true; }
trap cleanup EXIT
for _ in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8765/llb/cases/ >/dev/null; then
    break
  fi
  sleep 1
done
printf 'name\tcode\ttype\tbytes\n' > "$evidence/local-curl.tsv"
while IFS=$'\t' read -r name path; do
  metrics=$(curl -sS -o "$evidence/$name.body" -w '%{http_code}\t%{content_type}\t%{size_download}' "http://127.0.0.1:8765$path")
  printf '%s\t%s\n' "$name" "$metrics" >> "$evidence/local-curl.tsv"
done <<'ROUTES'
root	/llb/
cases	/llb/cases/
maneka	/llb/cases/sc-1978-maneka-gandhi-v-union-of-india/
review	/llb/cases/review/
trail	/llb/cases/trails/liberty-due-process-and-privacy/
styles	/llb/styles.css
case-css	/llb/case.css
case-js	/llb/case.js
cases-index	/llb/data/cases-index.json
worker	/llb/sw.js
offline	/llb/offline.html
ROUTES
cat "$evidence/local-curl.tsv"
awk -F '\t' 'NR > 1 && $2 != 200 { bad=1 } END { exit bad }' "$evidence/local-curl.tsv"
cleanup
trap - EXIT

git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git add -A
if git diff --cached --quiet; then
  echo "Generated root already matches the validated build."
else
  git commit -m "Publish complete styled LL.B. case catalogue and repair nested routes"
  git push origin HEAD:main
fi
git rev-parse HEAD | tee "$evidence/generated-commit.txt"
git status --short | tee "$evidence/git-status.txt"
