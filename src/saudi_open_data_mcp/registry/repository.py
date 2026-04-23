"""SQLite-backed registry repository."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .models import DatasetDescriptor, HealthMetadata


@dataclass(frozen=True)
class SeedDatasetResult:
    """Outcome of reconciling one seeded descriptor into the persistent registry."""

    dataset_id: str
    action: str
    changed_fields: tuple[str, ...] = ()


class RegistryRepository:
    """Persist registry metadata as typed SQLite-backed records."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def initialize(self) -> None:
        """Create the minimum schema required by the current registry models."""

        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS dataset_descriptors (
                    dataset_id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    source_locator TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    schema_version TEXT NOT NULL,
                    update_frequency TEXT NOT NULL,
                    health_status TEXT NOT NULL,
                    coverage_status TEXT NOT NULL,
                    caveats_json TEXT NOT NULL,
                    known_issues_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS dataset_health (
                    dataset_id TEXT PRIMARY KEY,
                    health_status TEXT NOT NULL
                );
                """
            )
            self._ensure_dataset_descriptor_columns(connection)

    def upsert_dataset(self, descriptor: DatasetDescriptor) -> None:
        """Insert or replace a dataset descriptor and its minimal health state."""

        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO dataset_descriptors (
                    dataset_id,
                    source,
                    source_locator,
                    title,
                    description,
                    schema_version,
                    update_frequency,
                    health_status,
                    coverage_status,
                    caveats_json,
                    known_issues_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    descriptor.dataset_id,
                    descriptor.source,
                    descriptor.source_locator,
                    descriptor.title,
                    descriptor.description,
                    descriptor.schema_version,
                    descriptor.update_frequency.value,
                    descriptor.health_status.value,
                    descriptor.coverage_status.value,
                    self._dump_notes(descriptor.caveats),
                    self._dump_notes(descriptor.known_issues),
                ),
            )
            connection.execute(
                """
                INSERT OR REPLACE INTO dataset_health (dataset_id, health_status)
                VALUES (?, ?)
                """,
                (descriptor.dataset_id, descriptor.health_status.value),
            )

    def seed_dataset(self, descriptor: DatasetDescriptor) -> SeedDatasetResult:
        """Insert or reconcile a bootstrap descriptor while preserving health state."""

        with self._connect() as connection:
            existing_row = connection.execute(
                """
                SELECT
                    dataset_id,
                    source,
                    source_locator,
                    title,
                    description,
                    schema_version,
                    update_frequency,
                    health_status,
                    coverage_status,
                    caveats_json,
                    known_issues_json
                FROM dataset_descriptors
                WHERE dataset_id = ?
                """,
                (descriptor.dataset_id,),
            ).fetchone()
            if existing_row is not None:
                existing_descriptor = self._descriptor_from_row(existing_row)
                existing_health = connection.execute(
                    """
                    SELECT health_status
                    FROM dataset_health
                    WHERE dataset_id = ?
                    """,
                    (descriptor.dataset_id,),
                ).fetchone()
                preserved_health_status = (
                    existing_health["health_status"]
                    if existing_health is not None
                    else existing_descriptor.health_status.value
                )
                changed_fields = self._seed_changed_fields(
                    existing_descriptor,
                    descriptor,
                )
                connection.execute(
                    """
                    INSERT OR IGNORE INTO dataset_health (dataset_id, health_status)
                    VALUES (?, ?)
                    """,
                    (descriptor.dataset_id, preserved_health_status),
                )
                if not changed_fields:
                    return SeedDatasetResult(
                        dataset_id=descriptor.dataset_id,
                        action="unchanged",
                    )

                connection.execute(
                    """
                    UPDATE dataset_descriptors
                    SET
                        source = ?,
                        source_locator = ?,
                        title = ?,
                        description = ?,
                        schema_version = ?,
                        update_frequency = ?,
                        health_status = ?,
                        coverage_status = ?,
                        caveats_json = ?,
                        known_issues_json = ?
                    WHERE dataset_id = ?
                    """,
                    (
                        descriptor.source,
                        descriptor.source_locator,
                        descriptor.title,
                        descriptor.description,
                        descriptor.schema_version,
                        descriptor.update_frequency.value,
                        preserved_health_status,
                        descriptor.coverage_status.value,
                        self._dump_notes(descriptor.caveats),
                        self._dump_notes(descriptor.known_issues),
                        descriptor.dataset_id,
                    ),
                )
                return SeedDatasetResult(
                    dataset_id=descriptor.dataset_id,
                    action="updated",
                    changed_fields=changed_fields,
                )

            connection.execute(
                """
                INSERT INTO dataset_descriptors (
                    dataset_id,
                    source,
                    source_locator,
                    title,
                    description,
                    schema_version,
                    update_frequency,
                    health_status,
                    coverage_status,
                    caveats_json,
                    known_issues_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    descriptor.dataset_id,
                    descriptor.source,
                    descriptor.source_locator,
                    descriptor.title,
                    descriptor.description,
                    descriptor.schema_version,
                    descriptor.update_frequency.value,
                    descriptor.health_status.value,
                    descriptor.coverage_status.value,
                    self._dump_notes(descriptor.caveats),
                    self._dump_notes(descriptor.known_issues),
                ),
            )
            connection.execute(
                """
                INSERT OR IGNORE INTO dataset_health (dataset_id, health_status)
                VALUES (?, ?)
                """,
                (descriptor.dataset_id, descriptor.health_status.value),
            )
            return SeedDatasetResult(
                dataset_id=descriptor.dataset_id,
                action="inserted",
            )

    def get_dataset(self, dataset_id: str) -> DatasetDescriptor | None:
        """Return a typed dataset descriptor for ``dataset_id`` when present."""

        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    dataset_id,
                    source,
                    source_locator,
                    title,
                    description,
                    schema_version,
                    update_frequency,
                    health_status,
                    coverage_status,
                    caveats_json,
                    known_issues_json
                FROM dataset_descriptors
                WHERE dataset_id = ?
                """,
                (dataset_id,),
            ).fetchone()

        if row is None:
            return None

        return self._descriptor_from_row(row)

    def list_datasets(self) -> list[DatasetDescriptor]:
        """List all dataset descriptors ordered by title then dataset identifier."""

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    dataset_id,
                    source,
                    source_locator,
                    title,
                    description,
                    schema_version,
                    update_frequency,
                    health_status,
                    coverage_status,
                    caveats_json,
                    known_issues_json
                FROM dataset_descriptors
                ORDER BY title COLLATE NOCASE ASC, dataset_id ASC
                """
            ).fetchall()

        return [self._descriptor_from_row(row) for row in rows]

    def search_datasets(self, query: str) -> list[DatasetDescriptor]:
        """Search ``dataset_id`` and ``title`` using case-insensitive substring matching."""

        normalized_query = query.strip()
        if not normalized_query:
            return self.list_datasets()

        like_query = f"%{normalized_query.lower()}%"

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    dataset_id,
                    source,
                    source_locator,
                    title,
                    description,
                    schema_version,
                    update_frequency,
                    health_status,
                    coverage_status,
                    caveats_json,
                    known_issues_json
                FROM dataset_descriptors
                WHERE LOWER(dataset_id) LIKE ? OR LOWER(title) LIKE ?
                ORDER BY title COLLATE NOCASE ASC, dataset_id ASC
                """,
                (like_query, like_query),
            ).fetchall()

        return [self._descriptor_from_row(row) for row in rows]

    def upsert_health(self, metadata: HealthMetadata) -> None:
        """Insert or replace minimal health metadata and sync descriptor state when present."""

        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO dataset_health (dataset_id, health_status)
                VALUES (?, ?)
                """,
                (metadata.dataset_id, metadata.health_status.value),
            )
            connection.execute(
                """
                UPDATE dataset_descriptors
                SET health_status = ?
                WHERE dataset_id = ?
                """,
                (metadata.health_status.value, metadata.dataset_id),
            )

    def get_health(self, dataset_id: str) -> HealthMetadata | None:
        """Return minimal health metadata for ``dataset_id`` when present."""

        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT dataset_id, health_status
                FROM dataset_health
                WHERE dataset_id = ?
                """,
                (dataset_id,),
            ).fetchone()

        if row is None:
            return None

        return self._health_from_row(row)

    def list_health(self) -> list[HealthMetadata]:
        """List all stored health metadata ordered by dataset identifier."""

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT dataset_id, health_status
                FROM dataset_health
                ORDER BY dataset_id ASC
                """
            ).fetchall()

        return [self._health_from_row(row) for row in rows]

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _ensure_dataset_descriptor_columns(connection: sqlite3.Connection) -> None:
        """Add required descriptor columns for the current v0.1 schema when missing."""

        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(dataset_descriptors)")
        }
        if "source_locator" not in columns:
            connection.execute(
                """
                ALTER TABLE dataset_descriptors
                ADD COLUMN source_locator TEXT NOT NULL DEFAULT ''
                """
            )
        if "coverage_status" not in columns:
            connection.execute(
                """
                ALTER TABLE dataset_descriptors
                ADD COLUMN coverage_status TEXT NOT NULL DEFAULT 'catalog_only'
                """
            )

    @staticmethod
    def _dump_notes(notes: tuple[str, ...]) -> str:
        return json.dumps(list(notes), ensure_ascii=True)

    @staticmethod
    def _seed_changed_fields(
        existing_descriptor: DatasetDescriptor,
        descriptor: DatasetDescriptor,
    ) -> tuple[str, ...]:
        changed_fields: list[str] = []
        if existing_descriptor.source != descriptor.source:
            changed_fields.append("source")
        if existing_descriptor.source_locator != descriptor.source_locator:
            changed_fields.append("source_locator")
        if existing_descriptor.title != descriptor.title:
            changed_fields.append("title")
        if existing_descriptor.description != descriptor.description:
            changed_fields.append("description")
        if existing_descriptor.schema_version != descriptor.schema_version:
            changed_fields.append("schema_version")
        if existing_descriptor.update_frequency is not descriptor.update_frequency:
            changed_fields.append("update_frequency")
        if existing_descriptor.coverage_status is not descriptor.coverage_status:
            changed_fields.append("coverage_status")
        if existing_descriptor.caveats != descriptor.caveats:
            changed_fields.append("caveats")
        if existing_descriptor.known_issues != descriptor.known_issues:
            changed_fields.append("known_issues")
        return tuple(changed_fields)

    @staticmethod
    def _load_notes(raw_notes: str) -> tuple[str, ...]:
        decoded_notes = json.loads(raw_notes)
        if not isinstance(decoded_notes, list):
            raise ValueError("Registry notes storage must decode to a list.")

        return tuple(str(note) for note in decoded_notes)

    def _descriptor_from_row(self, row: sqlite3.Row) -> DatasetDescriptor:
        return DatasetDescriptor.model_validate(
            {
                "dataset_id": row["dataset_id"],
                "source": row["source"],
                "source_locator": row["source_locator"],
                "title": row["title"],
                "description": row["description"],
                "schema_version": row["schema_version"],
                "update_frequency": row["update_frequency"],
                "health_status": row["health_status"],
                "coverage_status": row["coverage_status"],
                "caveats": self._load_notes(row["caveats_json"]),
                "known_issues": self._load_notes(row["known_issues_json"]),
            }
        )

    @staticmethod
    def _health_from_row(row: sqlite3.Row) -> HealthMetadata:
        return HealthMetadata.model_validate(
            {
                "dataset_id": row["dataset_id"],
                "health_status": row["health_status"],
            }
        )
