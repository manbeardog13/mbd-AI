# Codex live continuity update

**Date:** 2026-07-15

**Status:** Partial live verification; final disabled-continuity control pending

This addendum records live observations made by a real Codex-hosted session
after Claude's builder audit. Host labels remain claimed local provenance; they
are not cryptographic attestations from OpenAI or Anthropic.

## Codex to Claude

- Topic: `nero-crosshost-equation-20260715-codex-01`
- Captured event: `4b445951236445c3bf9e6df13b68e946`
- Event hash: `3b63663951076cf47e9a5d721ab5be62e092585c1107344e9051c35e7bc4d57d`
- Stored equation: `(93817 * 271) - 44009`
- Claude received only the topic, retrieved the exact stored nonce and equation,
  and independently returned `25380398`.
- Claimed source: `codex`

## Claude to Codex

- Topic: `nero-crosshost-equation-20260715-claude-01`
- Captured event: `b9286ac8e21a490095bbac09af34dc31`
- Event hash: `bda17ed0ebe3f2a746705c6ea10a5b5e149bbe5c7549d4cf64a6647ab62be0af`
- Retrieved equation: `6274 * 383 + 9109 - 4425`
- Independently checked result: `2407626`
- Codex recall receipt: `81ece763c9ed4b7b8370ecc914cbe35d`
- Claimed source: `claude`

The reverse host disclosed its generated payload in its own final response, so
that leg proves transport and receipt agreement but was not a fully blind test.

## Integrity and remaining controls

After both handoffs, live verification reported two events, eight receipts, and
no integrity problems. The live database remains ignored and local; it is not
part of this evidence bundle.

Still required before `LIVE_BIDIRECTIONAL_VERIFIED`:

1. Unknown challenge returns `NOT_FOUND`.
2. Disabled target adapter returns `UNAVAILABLE` for an unseen challenge.
3. Correction is retrieved by both hosts while the old event remains
   `superseded`.
