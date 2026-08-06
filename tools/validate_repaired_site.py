#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.refs: list[str] = []
        self.ids: list[str] = []
        self.viewport = False
        self.styles: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        if values.get("id"):
            self.ids.append(values["id"])
        if tag == "meta" and values.get("name", "").lower() == "viewport":
            self.viewport = True
        if tag == "link" and values.get("href"):
            self.refs.append(values["href"])
            if "stylesheet" in values.get("rel", "").lower():
                self.styles.append(values["href"])
        if tag == "script" and values.get("src"):
            self.refs.append(values["src"])
        if tag == "a" and values.get("href"):
            self.refs.append(values["href"])

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("usage: validate_repaired_site.py SITE_ROOT REPORT_PATH")

    root = Path(sys.argv[1]).resolve()
    report_path = Path(sys.argv[2]).resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)

    graph = load_json(root / "data/curriculum.json")
    graph_report = load_json(root / "data/validation-report.json")
    content = load_json(root / "data/content-report.json")
    cases = load_json(root / "data/case-coverage-report.json")
    case_index = load_json(root / "data/cases-index.json")

    expected_graph = {
        "subjects": 45,
        "coreSubjects": 25,
        "electiveSubjects": 20,
        "modules": 384,
        "topics": 3882,
        "foundations": 26,
        "learnableNodes": 3908,
        "allNodes": 4337,
        "strictEdges": 4043,
        "contextEdges": 28,
        "subjectEdges": 120,
        "maxDepth": 477,
        "termCounts": {"1": 5, "2": 5, "3": 7, "4": 10, "5": 10, "6": 8},
    }
    expected_cases = {
        "cases": 254,
        "nodeEdges": 665,
        "mappedNodes": 548,
        "developmentLinks": 119,
        "directTreatmentEdges": 0,
        "trails": 27,
        "subjectsCovered": 45,
        "directOfficialSources": 6,
        "officialDiscoverySources": 234,
        "paragraphPinnedCases": 0,
        "nodePagesPatched": 4337,
        "nodePagesWithCases": 819,
    }

    assert graph_report["valid"] and all(graph_report["checks"].values()), graph_report
    assert graph["meta"]["stats"] == expected_graph, graph["meta"]["stats"]
    assert content["valid"] and all(content["checks"].values()), content
    assert content["completeCoverage"] is True
    assert content["pageCount"] == 4337
    assert content["wordCounts"]["minimum"] >= 2500, content["wordCounts"]
    assert cases["valid"] and all(cases["checks"].values()), cases
    for key, value in expected_cases.items():
        assert cases["stats"][key] == value, (key, cases["stats"][key], value)
    assert len(case_index) == 254

    required = (
        "index.html",
        "styles.css",
        "app.js",
        "node.css",
        "node.js",
        "case.css",
        "case.js",
        "sw.js",
        "404.html",
        "offline.html",
        "cases/index.html",
        "cases/sc-1978-maneka-gandhi-v-union-of-india/index.html",
        "cases/trails/index.html",
        "cases/compare/index.html",
        "cases/review/index.html",
        "cases/method/index.html",
        "data/curriculum.json",
        "data/content-index.json",
        "data/cases-index.json",
        "data/cases-full.json",
        "data/case-node-edges.json",
        "data/case-trails.json",
        "sitemap.xml",
        "robots.txt",
        ".nojekyll",
    )
    missing = [path for path in required if not (root / path).is_file()]
    assert not missing, missing

    home = (root / "index.html").read_text(encoding="utf-8")
    catalogue = (root / "cases/index.html").read_text(encoding="utf-8")
    maneka = (root / "cases/sc-1978-maneka-gandhi-v-union-of-india/index.html").read_text(encoding="utf-8")
    not_found = (root / "404.html").read_text(encoding="utf-8")
    worker = (root / "sw.js").read_text(encoding="utf-8")

    assert 'href="cases/"' in home and "Open case catalogue" in home
    assert "Indian Law Case Catalogue" in catalogue and "../case.css" in catalogue
    assert "Maneka Gandhi" in maneka and "../../case.css" in maneka
    assert "<style>" in not_found and "/llb/cases/" in not_found
    assert "offline.html" in worker and "du-llb-cases-v2" in worker
    assert "caches.match('./index.html')" not in worker

    broken: list[tuple[str, str]] = []
    duplicate_ids: list[str] = []
    missing_viewport: list[str] = []
    missing_style: list[str] = []
    local_refs = 0
    html_files = list(root.rglob("*.html"))

    for page in html_files:
        text = page.read_text(encoding="utf-8", errors="replace")
        parser = PageParser()
        parser.feed(text)
        relative_page = str(page.relative_to(root))

        if not parser.viewport:
            missing_viewport.append(relative_page)
        if len(parser.ids) != len(set(parser.ids)):
            duplicate_ids.append(relative_page)
        if page.name not in {"404.html", "offline.html"} and not parser.styles and "<style" not in text:
            missing_style.append(relative_page)

        for raw in parser.refs:
            ref = html.unescape(raw).strip()
            if (
                not ref
                or "${" in ref
                or ref.startswith(("#", "http:", "https:", "mailto:", "tel:", "javascript:", "data:"))
            ):
                continue
            path = unquote(urlsplit(ref).path)
            if not path:
                continue
            local_refs += 1
            if path.startswith("/llb/"):
                target = root / path.removeprefix("/llb/")
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
                broken.append((relative_page, ref))

    assert len(html_files) >= 4670, len(html_files)
    assert not broken[:20], broken[:20]
    assert not duplicate_ids, duplicate_ids[:20]
    assert not missing_viewport, missing_viewport[:20]
    assert not missing_style, missing_style[:20]

    result = {
        "valid": True,
        "htmlPages": len(html_files),
        "studyPages": content["pageCount"],
        "cases": cases["stats"]["cases"],
        "caseNodeEdges": cases["stats"]["nodeEdges"],
        "mappedNodes": cases["stats"]["mappedNodes"],
        "localReferences": local_refs,
        "brokenLinks": len(broken),
        "duplicateIds": len(duplicate_ids),
        "missingViewport": len(missing_viewport),
        "missingStyles": len(missing_style),
    }
    report_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
