# Curriculum graph schema

`data/curriculum.json` is the canonical machine-readable index.

## Node kinds

- `foundation` or `skill`: common learnable method node.
- `subject`: non-learnable paper container.
- `module`: non-learnable unit or topic-group container.
- `topic`: smallest learnable syllabus node.

Every learnable node has `prerequisites`, `unlocks`, `learningOrder`, `level`, `summary`, `eli15`, source metadata and a stable `notePath`.

## Edge kinds

- `prerequisite`: strict directed edge. The target may assume the source. These edges alone form the DAG and determine unlocks.
- `background`: useful prior knowledge but not required.
- `related`: navigational cross-reference; direction does not imply dependency.
- `subject-prerequisite`: collapsed overview edge between papers, stored separately in `subjectEdges`.

## Stable identity

Internal IDs use lower-case catalog identities such as `lb-102`, module IDs such as `lb-102.m01`, and topic IDs such as `lb-102.m01.s01`. Display codes and aliases may change without breaking links.
