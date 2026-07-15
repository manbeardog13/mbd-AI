-- Nero Cross-Host Continuity Ledger — schema v1
--
-- A cold, deterministic, same-machine ledger through which deliberately-selected
-- Nero memories are transported between Claude-hosted and Codex-hosted sessions.
-- This is NOT the standalone local Nero application store (data/memory.db); it is
-- a separate, purpose-built database at data/continuity/continuity.db.
--
-- Design notes:
--   * Rollback-journal mode, synchronous=FULL, foreign_keys=ON (set by the CLI).
--   * The events table is append-only. Corrections, revocations, and redactions
--     are themselves appended events; the `status` column on a target row is a
--     derived convenience cache, re-derivable from those control events.
--   * event_hash / receipt_hash chain IMMUTABLE fields plus the original content
--     hash — never the mutable plaintext — so an approved plaintext redaction
--     does not silently destroy chain verification.
--   * Hash chains are tamper-EVIDENT against mistakes and accidental corruption.
--     They are NOT tamper-PROOF against a local administrator (see the ADR).

-- ---------------------------------------------------------------------------
-- Schema / ledger metadata (single-row-per-key key/value register)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS schema_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- ---------------------------------------------------------------------------
-- Events — the append-only continuity ledger
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS events (
    event_id            TEXT    PRIMARY KEY,
    schema_version      INTEGER NOT NULL,
    global_sequence     INTEGER NOT NULL UNIQUE,
    created_at_utc      TEXT    NOT NULL,   -- when the content was authored
    recorded_at_utc     TEXT    NOT NULL,   -- when the ledger recorded it
    actor               TEXT    NOT NULL,   -- who invoked (e.g. toni-via-claude)
    event_type          TEXT    NOT NULL,   -- capture | correction | revocation | redaction
    scope               TEXT    NOT NULL,   -- handoff | durable
    source_host_claim   TEXT    NOT NULL,   -- CLAIMED provenance (not provider-attested)
    capture_method      TEXT    NOT NULL,   -- e.g. cli_explicit
    session_id          TEXT,               -- genuine session/message id when available
    topic               TEXT,               -- bounded label / challenge id
    payload             TEXT,               -- bounded plaintext (NULL once redacted)
    content_sha256      TEXT    NOT NULL,   -- hash of the ORIGINAL payload (immutable)
    privacy_class       TEXT    NOT NULL,   -- e.g. user_shared
    consent_basis       TEXT    NOT NULL,   -- e.g. explicit_handoff | explicit_durable
    expires_at_utc      TEXT,               -- NULL = no expiry
    status              TEXT    NOT NULL,   -- active|expired|superseded|conflicted|revoked|redacted
    supersedes_event_id TEXT,               -- correction target
    idempotency_key     TEXT    NOT NULL UNIQUE,
    previous_hash       TEXT    NOT NULL,
    event_hash          TEXT    NOT NULL,
    metadata            TEXT,               -- bounded JSON

    CHECK (event_type IN ('capture','correction','revocation','redaction')),
    CHECK (scope IN ('handoff','durable')),
    CHECK (status IN ('active','expired','superseded','conflicted','revoked','redacted')),
    FOREIGN KEY (supersedes_event_id) REFERENCES events(event_id)
);

CREATE INDEX IF NOT EXISTS idx_events_topic    ON events(topic);
CREATE INDEX IF NOT EXISTS idx_events_status   ON events(status);
CREATE INDEX IF NOT EXISTS idx_events_seq       ON events(global_sequence);
CREATE INDEX IF NOT EXISTS idx_events_supersede ON events(supersedes_event_id);

-- ---------------------------------------------------------------------------
-- Durable memory — approved, long-lived statements (each linked to a source event)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS durable_memory (
    memory_id            TEXT    PRIMARY KEY,
    statement            TEXT    NOT NULL,
    kind                 TEXT    NOT NULL,   -- fact|preference|procedure|lesson|identity|correction
    status               TEXT    NOT NULL,   -- candidate|active|superseded|revoked|redacted
    importance           REAL    NOT NULL DEFAULT 0.5,
    confidence           REAL    NOT NULL DEFAULT 0.5,
    proposed_by          TEXT    NOT NULL,
    approved_by          TEXT,               -- NULL until Toni approves
    created_at_utc       TEXT    NOT NULL,
    supersedes_memory_id TEXT,
    content_sha256       TEXT    NOT NULL,
    source_event_id      TEXT    NOT NULL,   -- REQUIRED link; no source => cannot be active

    CHECK (kind IN ('fact','preference','procedure','lesson','identity','correction')),
    CHECK (status IN ('candidate','active','superseded','revoked','redacted')),
    FOREIGN KEY (source_event_id) REFERENCES events(event_id),
    FOREIGN KEY (supersedes_memory_id) REFERENCES durable_memory(memory_id)
);

CREATE INDEX IF NOT EXISTS idx_mem_status ON durable_memory(status);
CREATE INDEX IF NOT EXISTS idx_mem_source ON durable_memory(source_event_id);

-- ---------------------------------------------------------------------------
-- Receipts — one per operation, hash-chained
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS receipts (
    receipt_id            TEXT    PRIMARY KEY,
    correlation_id        TEXT    NOT NULL,
    receipt_seq           INTEGER NOT NULL UNIQUE,
    action                TEXT    NOT NULL,
    host_claim            TEXT    NOT NULL,   -- CLAIMED reader/writer host
    session_id            TEXT,               -- genuine when available
    selected_ids          TEXT,               -- JSON array of event/memory ids
    observed_payload_hash TEXT,               -- hash of payload observed (no plaintext)
    query_hash            TEXT,               -- hash of query (no plaintext query stored)
    result_code           TEXT    NOT NULL,
    created_at_utc        TEXT    NOT NULL,
    previous_hash         TEXT    NOT NULL,
    receipt_hash          TEXT    NOT NULL,
    meta                  TEXT                -- bounded JSON (never plaintext query/payload)
);

CREATE INDEX IF NOT EXISTS idx_receipts_seq    ON receipts(receipt_seq);
CREATE INDEX IF NOT EXISTS idx_receipts_corr   ON receipts(correlation_id);

-- ---------------------------------------------------------------------------
-- Host cursors — highest deliberately inspected sequence per host.
-- A cursor is a bookmark, NOT a wake signal: nothing polls or reacts to it.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS host_cursors (
    host                    TEXT    PRIMARY KEY,
    last_inspected_sequence INTEGER NOT NULL DEFAULT 0,
    updated_at_utc          TEXT    NOT NULL
);
