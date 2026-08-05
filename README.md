# DU LL.B. Knowledge Graph

A mobile-first, static prerequisite graph and note index for the University of Delhi LL.B. course-material catalog.

[Open the deployed index](https://legedith.github.io/llb/) · [Open the canonical DU catalog](https://lawfaculty.du.ac.in/Students/LL.B.-Course-Materials)

## What is here

- 45 papers across six terms: 25 core and 20 elective.
- 384 modules and 3882 syllabus-derived topic nodes.
- 26 common legal-method nodes.
- 4043 strict prerequisite edges, validated as a directed acyclic graph.
- Separate background and related edges, which never block progress.
- One stable Markdown note scaffold per paper, with an anchor for every topic node.
- Source, edition, code-alias and current-law warnings kept in node metadata.

## The key design rule

A strict prerequisite is material a later node may assume. Background reading is useful but optional. A related link is only a cross-reference. Keeping these relations separate prevents the rich legal cross-reference network from creating false learning cycles.

The DU term order is preserved for source fidelity. The learning view uses a topological order derived from strict prerequisites. These are intentionally different views.

## Repository map

- `index.html`, `styles.css`, `app.js`: zero-dependency mobile-first application.
- `data/curriculum.json`: complete machine-readable graph.
- `data/schema.md`: node and edge contract.
- `data/validation-report.json`: generated integrity checks and known source warnings.
- `notes/`: common foundations plus 45 subject note scaffolds.
- `subjects/`: human-readable subject indexes.
- `sources/README.md`: source register.

## Source discipline

The linked DU PDFs are course material, not proof of current law. Before a substantive note is treated as current, verify commencement, amendment, repeal, replacement codes, rules, notifications, binding later judgments and jurisdiction. Archive and outline-only sources are labelled rather than silently upgraded.

Do not mirror or reproduce substantial copyrighted course material. Quote only what is necessary, use pinpoint attribution, prefer public-domain primary law, and write original explanations.

## Local preview

```bash
python -m http.server 8000
```

Open `http://localhost:8000/`. The site uses no build step.
