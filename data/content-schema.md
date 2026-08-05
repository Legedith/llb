# Dedicated study-page schema

Content model: `3.0.0`

Every node in `data/curriculum.json` must resolve to `nodes/<node-id>/index.html`. All pages must include these stable section IDs:

- `orientation`
- `eli15`
- `outcomes`
- `prerequisite-bridge`
- `concept-map`
- `core-note`
- `issue-method`
- `boundaries`
- `authority-map`
- `worked-problem`
- `exam-method`
- `revision`
- `self-test`
- `sources`
- `progression`

## Integrity requirements

1. A page must remain readable even when its strict prerequisites are incomplete.
2. It may assume only nodes listed in its `prerequisites` array.
3. It must distinguish primary law, binding precedent, evidence, procedure, and remedy.
4. It must not invent statutory wording, quotations, case facts, holdings, empirical data, or current-law status.
5. It must identify the DU course source and state that the syllabus edition is not proof of current law.
6. It must contain a worked problem, exam method, revision material, model-answer self-test, and progression links.
7. Shared progress state uses `du-llb-graph-v1`.

`data/content-report.json` records coverage, minimum and average page length, required-section checks, routing checks, and forbidden-marker checks.
