"""Idempotent schema for the generic material core."""
import sqlite3


MATERIAL_SCHEMA_VERSION = 17


def _add_column_if_missing(
    conn: sqlite3.Connection, table: str, column: str, definition: str
) -> None:
    columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _allow_multiple_candidates_per_job(conn: sqlite3.Connection) -> None:
    """Remove the M4 one-candidate-per-job constraint without losing rows."""
    for index in conn.execute("PRAGMA index_list(candidates)").fetchall():
        if not index[2]:
            continue
        columns = [row[2] for row in conn.execute(f"PRAGMA index_info({index[1]})")]
        if columns != ["job_id"]:
            continue
        conn.executescript("""
            CREATE TABLE candidates_v2 (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id            INTEGER NOT NULL REFERENCES collection_jobs(id) ON DELETE CASCADE,
                title             TEXT NOT NULL,
                content_text      TEXT NOT NULL,
                summary           TEXT,
                source_kind       TEXT NOT NULL,
                source_url        TEXT NOT NULL,
                content_hash      TEXT NOT NULL,
                source_facts_json TEXT NOT NULL DEFAULT '{}',
                status            TEXT NOT NULL DEFAULT 'pending',
                accepted_item_id  INTEGER REFERENCES items(id) ON DELETE SET NULL,
                created_at        TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at        TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(job_id, source_url),
                CHECK(status IN ('pending', 'accepted', 'rejected'))
            );
            INSERT INTO candidates_v2
                (id, job_id, title, content_text, summary, source_kind, source_url,
                 content_hash, source_facts_json, status, accepted_item_id, created_at, updated_at)
            SELECT id, job_id, title, content_text, summary, source_kind, source_url,
                   content_hash, source_facts_json, status, accepted_item_id, created_at, updated_at
            FROM candidates;
            DROP TABLE candidates;
            ALTER TABLE candidates_v2 RENAME TO candidates;
        """)
        break


def ensure_material_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS schema_meta (
            key         TEXT PRIMARY KEY,
            value       TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS items (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            item_type       TEXT NOT NULL DEFAULT 'general',
            title           TEXT NOT NULL,
            content_text    TEXT NOT NULL,
            summary         TEXT,
            source_kind     TEXT NOT NULL DEFAULT 'text_import',
            source_url      TEXT,
            status          TEXT NOT NULL DEFAULT 'inbox',
            tags_json       TEXT NOT NULL DEFAULT '[]',
            metadata_json   TEXT NOT NULL DEFAULT '{}',
            content_hash    TEXT NOT NULL UNIQUE,
            created_at      TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS assets (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id         INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
            asset_kind      TEXT NOT NULL,
            original_name   TEXT,
            storage_path    TEXT NOT NULL,
            mime_type       TEXT,
            content_hash    TEXT NOT NULL,
            size_bytes      INTEGER NOT NULL,
            image_width     INTEGER,
            image_height    INTEGER,
            created_at      TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS extraction_runs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id         INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
            processor       TEXT NOT NULL,
            processor_version TEXT NOT NULL,
            run_kind        TEXT NOT NULL,
            status          TEXT NOT NULL,
            input_hash      TEXT NOT NULL,
            result_json     TEXT,
            error_message   TEXT,
            provider        TEXT,
            model           TEXT,
            provider_model  TEXT,
            input_tokens    INTEGER,
            output_tokens   INTEGER,
            duration_ms     INTEGER,
            request_id      TEXT,
            prompt_version  TEXT,
            created_at      TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS accepted_extractions (
            item_id          INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
            extraction_kind  TEXT NOT NULL,
            run_id           INTEGER NOT NULL REFERENCES extraction_runs(id) ON DELETE RESTRICT,
            text_value       TEXT NOT NULL,
            accepted_at      TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at       TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY(item_id, extraction_kind)
        );

        CREATE TABLE IF NOT EXISTS item_relations (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            from_item_id    INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
            to_item_id      INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
            relation_type   TEXT NOT NULL,
            score           REAL,
            evidence_json   TEXT NOT NULL DEFAULT '{}',
            created_at      TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(from_item_id, to_item_id, relation_type),
            CHECK(from_item_id != to_item_id)
        );

        CREATE TABLE IF NOT EXISTS item_template_data (
            item_id          INTEGER PRIMARY KEY REFERENCES items(id) ON DELETE CASCADE,
            template_key     TEXT NOT NULL,
            schema_version   INTEGER NOT NULL,
            extracted_json   TEXT NOT NULL DEFAULT '{}',
            confirmed_json   TEXT NOT NULL DEFAULT '{}',
            extractor        TEXT,
            extractor_version TEXT,
            extracted_at     TEXT,
            confirmed_at     TEXT,
            updated_at       TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS action_projects (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            title           TEXT NOT NULL,
            objective       TEXT NOT NULL DEFAULT '',
            notes           TEXT NOT NULL DEFAULT '',
            next_action     TEXT NOT NULL DEFAULT '',
            status          TEXT NOT NULL DEFAULT 'active',
            created_at      TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
            CHECK(status IN ('active', 'completed', 'archived'))
        );

        CREATE TABLE IF NOT EXISTS action_project_items (
            project_id      INTEGER NOT NULL REFERENCES action_projects(id) ON DELETE CASCADE,
            item_id         INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
            position        INTEGER NOT NULL,
            added_at        TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY(project_id, item_id),
            UNIQUE(project_id, position)
        );

        CREATE TABLE IF NOT EXISTS collection_jobs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            collector       TEXT NOT NULL,
            query_json      TEXT NOT NULL DEFAULT '{}',
            status          TEXT NOT NULL DEFAULT 'pending',
            candidate_count INTEGER NOT NULL DEFAULT 0,
            accepted_count  INTEGER NOT NULL DEFAULT 0,
            error_message   TEXT,
            created_at      TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS candidates (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id          INTEGER NOT NULL REFERENCES collection_jobs(id) ON DELETE CASCADE,
            title           TEXT NOT NULL,
            content_text    TEXT NOT NULL,
            summary         TEXT,
            source_kind     TEXT NOT NULL,
            source_url      TEXT NOT NULL,
            content_hash    TEXT NOT NULL,
            canonical_id    TEXT,
            source_facts_json TEXT NOT NULL DEFAULT '{}',
            status          TEXT NOT NULL DEFAULT 'pending',
            accepted_item_id INTEGER REFERENCES items(id) ON DELETE SET NULL,
            created_at      TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(job_id, source_url),
            CHECK(status IN ('pending', 'accepted', 'rejected'))
        );

        CREATE TABLE IF NOT EXISTS item_external_identities (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id          INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
            identity_type    TEXT NOT NULL,
            normalized_value TEXT NOT NULL,
            created_at       TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(identity_type, normalized_value),
            UNIQUE(item_id, identity_type, normalized_value)
        );

        CREATE TABLE IF NOT EXISTS candidate_source_records (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_id      INTEGER NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
            job_id            INTEGER NOT NULL REFERENCES collection_jobs(id) ON DELETE CASCADE,
            source_kind       TEXT NOT NULL,
            source_record_id  TEXT,
            status            TEXT NOT NULL,
            facts_json        TEXT NOT NULL DEFAULT '{}',
            error_message     TEXT,
            fetched_at        TEXT,
            created_at        TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(job_id, candidate_id, source_kind),
            CHECK(status IN ('succeeded', 'failed'))
        );

        CREATE TABLE IF NOT EXISTS saved_discovery_rules (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            source_kind TEXT NOT NULL,
            query_json  TEXT NOT NULL,
            last_run_at TEXT,
            last_run_status TEXT,
            last_error TEXT,
            last_success_at TEXT,
            last_successful_job_id INTEGER REFERENCES collection_jobs(id) ON DELETE SET NULL,
            created_at  TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
            CHECK(source_kind IN ('crossref_ieee'))
        );

        CREATE TABLE IF NOT EXISTS chat_sessions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            title           TEXT NOT NULL DEFAULT '新对话',
            created_at      TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS chat_turns (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id        INTEGER NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
            user_message      TEXT NOT NULL,
            assistant_message TEXT,
            status            TEXT NOT NULL DEFAULT 'running',
            paper_ids_json     TEXT NOT NULL DEFAULT '[]',
            input_scope_json   TEXT NOT NULL DEFAULT '[]',
            history_turn_ids_json TEXT NOT NULL DEFAULT '[]',
            provider          TEXT,
            model             TEXT,
            provider_model    TEXT,
            input_tokens      INTEGER,
            output_tokens     INTEGER,
            duration_ms       INTEGER,
            request_id        TEXT,
            prompt_version    TEXT NOT NULL DEFAULT 'paper-chat-v1',
            error_message     TEXT,
            created_at        TEXT NOT NULL DEFAULT (datetime('now')),
            completed_at      TEXT,
            CHECK(status IN ('running', 'succeeded', 'failed'))
        );

        CREATE TABLE IF NOT EXISTS paper_ai_runs (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            paper_id          INTEGER REFERENCES papers(id) ON DELETE CASCADE,
            paper_ids_json    TEXT NOT NULL DEFAULT '[]',
            run_kind          TEXT NOT NULL,
            status            TEXT NOT NULL DEFAULT 'running',
            input_scope_json  TEXT NOT NULL DEFAULT '[]',
            input_hash        TEXT NOT NULL,
            processor         TEXT NOT NULL,
            processor_version TEXT NOT NULL,
            prompt_version    TEXT NOT NULL,
            provider          TEXT,
            model             TEXT,
            provider_model    TEXT,
            input_tokens      INTEGER,
            output_tokens     INTEGER,
            duration_ms       INTEGER,
            request_id        TEXT,
            result_json       TEXT,
            error_message     TEXT,
            created_at        TEXT NOT NULL DEFAULT (datetime('now')),
            completed_at      TEXT,
            CHECK(status IN ('running', 'succeeded', 'failed'))
        );

        CREATE TABLE IF NOT EXISTS candidate_ai_runs (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_ids_json TEXT NOT NULL DEFAULT '[]',
            status            TEXT NOT NULL DEFAULT 'running',
            input_scope_json  TEXT NOT NULL DEFAULT '[]',
            input_hash        TEXT NOT NULL,
            processor         TEXT NOT NULL,
            processor_version TEXT NOT NULL,
            prompt_version    TEXT NOT NULL,
            provider          TEXT,
            model             TEXT,
            provider_model    TEXT,
            input_tokens      INTEGER,
            output_tokens     INTEGER,
            duration_ms       INTEGER,
            request_id        TEXT,
            result_json       TEXT,
            error_message     TEXT,
            created_at        TEXT NOT NULL DEFAULT (datetime('now')),
            completed_at      TEXT,
            CHECK(status IN ('running', 'succeeded', 'failed'))
        );

        CREATE INDEX IF NOT EXISTS idx_items_type ON items(item_type);
        CREATE INDEX IF NOT EXISTS idx_items_status ON items(status);
        CREATE INDEX IF NOT EXISTS idx_items_created ON items(created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_assets_item ON assets(item_id);
        CREATE INDEX IF NOT EXISTS idx_extractions_item ON extraction_runs(item_id);
        CREATE INDEX IF NOT EXISTS idx_accepted_extractions_run ON accepted_extractions(run_id);
        CREATE INDEX IF NOT EXISTS idx_relations_from ON item_relations(from_item_id);
        CREATE INDEX IF NOT EXISTS idx_relations_to ON item_relations(to_item_id);
        CREATE INDEX IF NOT EXISTS idx_templates_key ON item_template_data(template_key);
        CREATE INDEX IF NOT EXISTS idx_action_projects_status ON action_projects(status, updated_at DESC);
        CREATE INDEX IF NOT EXISTS idx_action_project_items_item ON action_project_items(item_id);
        CREATE INDEX IF NOT EXISTS idx_chat_sessions_updated ON chat_sessions(updated_at DESC);
        CREATE INDEX IF NOT EXISTS idx_chat_turns_session ON chat_turns(session_id, id);
        CREATE INDEX IF NOT EXISTS idx_paper_ai_runs_paper ON paper_ai_runs(paper_id, id DESC);
        CREATE INDEX IF NOT EXISTS idx_paper_ai_runs_kind ON paper_ai_runs(run_kind, id DESC);
        CREATE INDEX IF NOT EXISTS idx_candidate_ai_runs_id ON candidate_ai_runs(id DESC);
    """)
    _allow_multiple_candidates_per_job(conn)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_candidates_status ON candidates(status, created_at DESC)"
    )
    _add_column_if_missing(conn, "saved_discovery_rules", "last_run_at", "TEXT")
    _add_column_if_missing(conn, "saved_discovery_rules", "last_run_status", "TEXT")
    _add_column_if_missing(conn, "saved_discovery_rules", "last_error", "TEXT")
    _add_column_if_missing(conn, "saved_discovery_rules", "last_success_at", "TEXT")
    _add_column_if_missing(
        conn, "saved_discovery_rules", "last_successful_job_id",
        "INTEGER REFERENCES collection_jobs(id) ON DELETE SET NULL",
    )
    _add_column_if_missing(
        conn, "extraction_runs", "input_scope_json", "TEXT NOT NULL DEFAULT '[]'"
    )
    _add_column_if_missing(
        conn, "extraction_runs", "input_item_ids_json", "TEXT NOT NULL DEFAULT '[]'"
    )
    _add_column_if_missing(conn, "assets", "image_width", "INTEGER")
    _add_column_if_missing(conn, "assets", "image_height", "INTEGER")
    _add_column_if_missing(conn, "candidates", "canonical_id", "TEXT")
    _add_column_if_missing(conn, "collection_jobs", "result_json", "TEXT NOT NULL DEFAULT '{}'")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_candidates_canonical ON candidates(canonical_id)"
    )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_candidates_job_canonical "
        "ON candidates(job_id, canonical_id) WHERE canonical_id IS NOT NULL"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_item_identities_item ON item_external_identities(item_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_candidate_sources_candidate "
        "ON candidate_source_records(candidate_id, id DESC)"
    )
    for column, definition in (
        ("provider_model", "TEXT"),
        ("input_tokens", "INTEGER"),
        ("output_tokens", "INTEGER"),
        ("duration_ms", "INTEGER"),
        ("request_id", "TEXT"),
    ):
        _add_column_if_missing(conn, "extraction_runs", column, definition)
    _add_column_if_missing(
        conn, "chat_turns", "prompt_version", "TEXT NOT NULL DEFAULT 'paper-chat-v1'"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_extractions_reuse "
        "ON extraction_runs(item_id, run_kind, input_hash, status)"
    )
    conn.execute(
        "INSERT INTO schema_meta(key, value) VALUES('material_schema_version', ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (str(MATERIAL_SCHEMA_VERSION),),
    )
