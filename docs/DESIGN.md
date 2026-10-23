# Design

## 1. First principles

A memory system is worth what it can **retrieve correctly** and how well it
**refuses to treat wrong things as facts**. Storage volume is not the metric.

Three constraints follow:

1. Writing must be near-free, or nobody writes. Ingestion runs in the
   background, not as a chore.
2. Retrieval must be layered before it is merged: facts from mem0, knowledge
   from Obsidian, raw evidence from files.
3. One piece of content has exactly one primary copy. The other layer may hold
   a pointer, never a duplicate.

## 2. Two layers

| Layer | Stores | Never stores | Retrieval |
|---|---|---|---|
| mem0 | atomic facts, preferences, decisions, project state, experiences, intentions | long-form methods, full notes, raw conversations, credentials | semantic search inside a `user_id` namespace |
| Obsidian | reusable knowledge: methods, criteria, protocols, lessons | fact streams, raw sessions | full-text / wiki search |

Routing:

- fact -> mem0 (primary), nothing in Obsidian
- knowledge -> Obsidian (primary), one short pointer in mem0
- conversation -> extract knowledge to Obsidian; store only topic/outcome in mem0
- credentials / raw bodies -> nowhere

## 3. Classification

Borrowed from Hy-Memory's scene/layer split:

| scene | layer | use |
|---|---|---|
| chat | L0 | basic user/environment info |
| chat | L2 | atomic facts |
| chat | L3 | session/day summaries |
| chat | L7 | intentions with an expiry |
| working | fact | what one delivery did |
| working | experience | reusable approach |
| coding | fact / experience | code decisions and changes |

Metadata travels with every memory so retrieval can filter by `scene`,
`category`, `status` and `date`.

## 4. Failure modes this repo encodes

### 4.1 Exit code is not delivery

A sandboxed child process may be unable to run the tool at all. If the parent
only checks `exit code 0`, the log looks healthy while nothing was sent.
**Invariant:** the component with credentials owns the side effect; the model
only produces text.

### 4.2 Encoding at the process boundary

Reading a UTF-8 stream with the ANSI code page garbles CJK and breaks JSON in
the middle of a string. **Invariant:** set the encoding explicitly on every
child process and every file read/write.

### 4.3 No replay

Servers generally do not replay already-delivered messages. One failed parse
means a permanent gap. **Invariant:** reconcile periodically against a
`needs_reply`-style source of truth, in addition to a cursor.

### 4.4 Duplicate writes

Re-running extraction produces near-duplicates. **Invariant:** normalize the
text, hash it, and keep an append-only ledger; skip on hit.

## 5. Guardrails

- Redaction before any network call: keys, emails, absolute paths.
- `--no-infer` for exact facts; inference is a deliberate choice, not a default.
- Auto-replies: daily cap, per-sender cooldown, `Auto-Submitted` header.
- Every write is append-only; deletion is an explicit, scoped operation.

## 6. What this repo deliberately does not do

- No vector index over raw sessions: the raw files are local and searchable;
  adding embeddings first adds maintenance cost without a demonstrated query.
- No gateway server: the CLI plus the two layers already answer the questions.
- No cross-agent namespace tree: `user_id` plus metadata is enough until a
  second agent actually shares the store.

Those are choices, not omissions: add them when a query demands it.
