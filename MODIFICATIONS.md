# Modifications

This repository is a derivative of **OpenAI Codex** (https://github.com/openai/codex),
licensed under the Apache License 2.0. Per Apache-2.0 §4(b), the changes made
relative to the upstream source are stated below.

It is an **unofficial** fork and is **not affiliated with or endorsed by OpenAI**.

## Summary of changes
- **Added `lean-prover/`** — a token-efficiency optimisation layer that specialises
  the agent for autonomous Lean 4 / Mathlib formalisation (purpose-built system
  prompt, tool-set cull, sandbox-only config, compiler-output filter, and an
  exact token-accounting harness). See `lean-prover/README.md`.
- **Added a debug helper** in `codex-rs/core/src/prompt_debug.rs`
  (`build_request_debug`) plus a test (`core/tests/suite/prompt_debug_tests.rs::
  dump_real_request`) and an export in `codex-rs/core/src/lib.rs`. These dump the
  exact serialized Responses-API request so per-turn token cost can be measured
  rather than estimated. They are additive and do not change agent behaviour.
- **Removed** the unrelated cyber-security guardrail-ablation variants that exist
  in the private upstream working tree (`variants/`). They are not part of this
  build and are excluded from this public repository.

## Upstream
- Project: OpenAI Codex — https://github.com/openai/codex
- License: Apache License 2.0 (see `LICENSE`)
- Attribution: see `NOTICE`
