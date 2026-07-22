# Agent skills

## Issue tracker

Issues are tracked on GitHub. See `docs/agents/issue-tracker.md`.

## Triage labels

The triage skill uses the default five-label vocabulary. See `docs/agents/triage-labels.md`.

## Domain docs

Single-context layout (one `CONTEXT.md` + `docs/adr/` at repo root). See `docs/agents/domain.md`.

## Project Memories & Feedback

### 1. Spec Fidelis over Abstraction (Avoid Speculative Generality)
- **Feedback**: Do not replace explicit, standalone helper functions requested in plans/specs with generic `TypeVar` utilities (e.g. `_resolve_env_number`). Keep implementation code aligned with the spec API signatures.

### 2. UI & Domain Boundary (Avoid Feature Envy)
- **Feedback**: UI controllers (`MenuHandlers`) should not extract private internal state directly from clients (e.g. `extract_session_id(self.client)`). Pass the client or service object directly to domain functions (`osint_profile(instagrapi_client=...)`) so session extraction happens inside the module.

### 3. CI Workflow Consistency
- **Feedback**: Follow the exact workflow step definitions in `plans/*.md` (such as `actions/setup-python@v5` + `pip install uv`) without introducing unrequested external actions or file pins unless explicitly specified.

### 4. Pre-flight Git Ref Validation
- **Feedback**: Before executing multi-agent code reviews, verify that the comparison ref (`fixed-point...HEAD`) resolves and produces a non-empty diff.
