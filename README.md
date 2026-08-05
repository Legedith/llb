# DU LL.B. Knowledge Graph and Study Library

A mobile-first prerequisite graph and complete dedicated-page study library for the University of Delhi LL.B. course-material catalog.

[Open the deployed library](https://legedith.github.io/llb/) · [Find a study node](https://legedith.github.io/llb/nodes/) · [Open the canonical DU catalog](https://lawfaculty.du.ac.in/Students/LL.B.-Course-Materials)

## Coverage

- 45 papers across six terms.
- 384 modules and 3882 syllabus-derived topics.
- 26 common legal-method foundations.
- 4337 dedicated static study pages.
- 4043 strict prerequisite edges, kept acyclic.
- Every page includes orientation, plain-language explanation, outcomes, prerequisite bridge, visual decision path, full study note, issue-and-proof method, boundaries, authority map, worked problem, exam guide, revision kit, self-test, source checks, and progression links.

## How it works

The graph index preserves readiness and progress. Opening a node now navigates to `nodes/<stable-id>/`, regardless of whether the node is ready or sequence-locked. A lock is only a learning-order signal; it never hides the study content.

Strict prerequisites are the only knowledge a later node may assume. Background and related links remain non-blocking cross-references. Progress and bookmarks are stored locally in the browser under the same state key used by the graph.

## Legal-content integrity

The pages provide original explanatory study content generated from the node title, paper, module, prerequisite structure, domain-specific legal method, concept-specific frameworks, legislation register, and official source trail. They do not fabricate statutory quotations, case facts, holdings, or later treatment. Where the graph supplies only the name of an authority, the page explains its curricular role and supplies a rigorous case-extraction method, while requiring verification against the judgment or reliable report.

The DU PDF edition identifies the syllabus, not necessarily current law. Before reliance, verify commencement, amendment, repeal or replacement, savings and transition, rules, notifications, later binding judgments, jurisdiction, forum, and limitation.

## Repository map

- `index.html`, `styles.css`, `app.js`: graph and curriculum navigator.
- `nodes/<id>/index.html`: one stable study page per graph node.
- `node.css`, `node.js`: shared mobile-first study-page interface and progress sync.
- `data/curriculum.json`: graph plus study-page metadata.
- `data/content-index.json`: searchable page register.
- `data/content-report.json`: generated coverage and quality validation.
- `data/content-schema.md`: study-page contract.
- `notes/`: paper and foundation source indexes linking to full pages.
- `tools/build_site.py`: curriculum graph generator.
- `tools/enrich_nodes.py`: dedicated study-page generator.

## Rebuild

The GitHub Actions workflow runs both generators, validates the graph, validates every page and required section, checks JavaScript syntax, replaces the deployed root, and commits the generated site to `main`.
