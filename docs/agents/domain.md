# Domain docs

Engineering skills should consume the repository's domain documentation as follows.

## Before exploring

- Read `CONTEXT.md` at the repository root when it exists.
- Read `CONTEXT-MAP.md` instead when it exists, then read the `CONTEXT.md` files relevant to the work.
- Read ADRs in `docs/adr/` that touch the area being changed.
- If these files do not exist, proceed silently; do not suggest creating them upfront.

## Layout

This repository uses the single-context layout:

```text
/
├── CONTEXT.md
├── docs/adr/
└── src/
```

The `domain-modeling` skill creates domain documentation lazily when terminology or architectural decisions need to be recorded.

## Vocabulary and decisions

Use terminology defined in `CONTEXT.md` for domain concepts. If a needed term is missing, treat that as a signal to clarify or record the gap rather than inventing a competing synonym. If proposed work conflicts with an existing ADR, surface the conflict explicitly.
