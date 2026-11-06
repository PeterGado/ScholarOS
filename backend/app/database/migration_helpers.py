"""Idempotent wrappers around Alembic's `op.*` DDL commands.

Why these exist (2026-11-06): every `op.create_table`/`op.add_column`/`op.create_index` in this
project's history assumed it ran against a database built by the migration before it. That is
true for a database created by `alembic upgrade head` from empty, and false for one that grew up
under `Base.metadata.create_all()` - the app's own startup bootstrap for its whole pre-Alembic
life (ADR-004/ADR-013). `create_all()` creates whatever tables the *current* models define, so a
database that was last started before the google-signin/email-verification migrations has every
table the baseline migration would create but not the columns those later migrations add.

Against such a database `alembic upgrade head` used to abort on its very first statement
(`table users already exists`) and could never be used to repair anything - which is exactly the
situation a 2026-11-06 local-dev crash left a developer in, with the migration path that every
document points to simply not working.

These helpers make each revision adopt what is already there instead of re-creating it, so
`upgrade head` can walk an existing database forward. They are no-ops on a fresh database
(the object is absent, so the underlying `op.*` call runs exactly as before), which is why the
normal `alembic upgrade head`-from-empty path is unchanged.

Deliberately *not* a general-purpose reconciliation layer: they skip DDL that already exists and
never compare column types, defaults, or nullability. Postgres-only raw-SQL DDL (RLS policies,
the restricted role, `NOT VALID` check constraints) is already written defensively where it needs
to be - `CREATE OR REPLACE FUNCTION`, `DO $$ ... IF NOT EXISTS`, `IF NOT EXISTS` on indexes -
because those are idempotent in SQL itself.
"""

from collections.abc import Iterable
from typing import Any

import sqlalchemy as sa

from alembic import op


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def has_table(table_name: str) -> bool:
    return bool(_inspector().has_table(table_name))


def existing_columns(table_name: str) -> set[str]:
    inspector = _inspector()
    if not inspector.has_table(table_name):
        return set()
    return {str(column["name"]) for column in inspector.get_columns(table_name)}


def existing_index_names(table_name: str) -> set[str]:
    inspector = _inspector()
    if not inspector.has_table(table_name):
        return set()
    return {str(index["name"]) for index in inspector.get_indexes(table_name)}


def existing_unique_constraint_names(table_name: str) -> set[str]:
    inspector = _inspector()
    if not inspector.has_table(table_name):
        return set()
    return {str(constraint["name"]) for constraint in inspector.get_unique_constraints(table_name) if constraint.get("name")}


def existing_check_constraint_names(table_name: str) -> set[str]:
    inspector = _inspector()
    if not inspector.has_table(table_name):
        return set()
    return {str(constraint["name"]) for constraint in inspector.get_check_constraints(table_name) if constraint.get("name")}


def create_table_if_missing(table_name: str, *args: Any, **kwargs: Any) -> None:
    """`op.create_table`, skipped when the table already exists."""
    if not has_table(table_name):
        op.create_table(table_name, *args, **kwargs)


def add_column_if_missing(table_name: str, column: sa.Column[Any], **kwargs: Any) -> None:
    """`op.add_column`, skipped when the column already exists."""
    if column.name not in existing_columns(table_name):
        op.add_column(table_name, column, **kwargs)


def create_index_if_missing(
    index_name: str, table_name: str, columns: Iterable[str], **kwargs: Any
) -> None:
    """`op.create_index`, skipped when an index of that name already exists."""
    if index_name not in existing_index_names(table_name):
        op.create_index(index_name, table_name, list(columns), **kwargs)
