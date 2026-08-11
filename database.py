"""Capa de base de datos dual para Floki Manager.

- SQLite cuando no existe DATABASE_URL (uso local/pruebas).
- PostgreSQL cuando DATABASE_URL comienza con postgres:// o postgresql://.

La aplicación histórica usa SQL con marcadores ``?``. Este módulo mantiene
esa interfaz y adapta las consultas para PostgreSQL sin obligar a reescribir
cada pantalla de una sola vez.
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Sequence

try:  # Solo es obligatorio cuando se usa PostgreSQL.
    import psycopg
    from psycopg.errors import IntegrityError as PostgresIntegrityError
except ImportError:  # pragma: no cover - el modo SQLite no lo necesita.
    psycopg = None

    class PostgresIntegrityError(Exception):
        pass


DB_INTEGRITY_ERRORS = (sqlite3.IntegrityError, PostgresIntegrityError)
SERIAL_ID_TABLES = {
    "users",
    "cash_sessions",
    "promoters",
    "beverage_products",
    "ticketing_products",
    "beverage_stock",
    "beverage_stock_adjustments",
    "birthday_benefits",
    "birthday_events",
    "promoter_guests",
    "guest_checkins",
    "list_imports",
    "movements",
    "offline_operations",
}


class DBRow(dict):
    """Fila compatible con sqlite3.Row: acceso por nombre y por posición."""

    def __init__(self, columns: Sequence[str], values: Sequence[Any]):
        super().__init__(zip(columns, values))
        self._columns = tuple(columns)
        self._values = tuple(values)

    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, int):
            return self._values[key]
        return super().__getitem__(key)

    def keys(self):  # noqa: D401 - conserva la API de sqlite3.Row.
        return super().keys()


class DBResult:
    def __init__(self, cursor=None, *, lastrowid=None, prefetched=None):
        self.cursor = cursor
        self.lastrowid = lastrowid
        self._prefetched = list(prefetched or [])
        self.rowcount = getattr(cursor, "rowcount", -1) if cursor is not None else 0

    def _columns(self) -> list[str]:
        if self.cursor is None or self.cursor.description is None:
            return []
        return [item.name if hasattr(item, "name") else item[0] for item in self.cursor.description]

    def _convert(self, row):
        if row is None:
            return None
        if isinstance(row, sqlite3.Row):
            return row
        if isinstance(row, DBRow):
            return row
        if isinstance(row, Mapping):
            return DBRow(list(row.keys()), list(row.values()))
        return DBRow(self._columns(), row)

    def fetchone(self):
        if self._prefetched:
            return self._convert(self._prefetched.pop(0))
        if self.cursor is None:
            return None
        return self._convert(self.cursor.fetchone())

    def fetchall(self):
        rows = self._prefetched
        self._prefetched = []
        if self.cursor is not None:
            rows.extend(self.cursor.fetchall())
        return [self._convert(row) for row in rows]


class DatabaseConnection:
    def __init__(self, connection, backend: str):
        self.connection = connection
        self.backend = backend

    @property
    def is_postgres(self) -> bool:
        return self.backend == "postgresql"

    def execute(self, sql: str, params: Sequence[Any] | None = None) -> DBResult:
        params = tuple(params or ())
        if not self.is_postgres:
            cursor = self.connection.execute(sql, params)
            return DBResult(cursor, lastrowid=cursor.lastrowid)

        translated, returns_id = translate_postgres_sql(sql, append_returning=True)
        cursor = self.connection.cursor()
        cursor.execute(translated, params)
        lastrowid = None
        prefetched = []
        if returns_id and cursor.description:
            row = cursor.fetchone()
            if row is not None:
                lastrowid = row[0]
        return DBResult(cursor, lastrowid=lastrowid, prefetched=prefetched)

    def executemany(self, sql: str, params: Iterable[Sequence[Any]]) -> DBResult:
        if not self.is_postgres:
            cursor = self.connection.executemany(sql, params)
            return DBResult(cursor, lastrowid=cursor.lastrowid)
        translated, _ = translate_postgres_sql(sql, append_returning=False)
        cursor = self.connection.cursor()
        cursor.executemany(translated, list(params))
        return DBResult(cursor)

    def executescript(self, script: str):
        if not self.is_postgres:
            return self.connection.executescript(script)
        for statement in split_sql_script(script):
            translated, _ = translate_postgres_sql(statement, append_returning=False)
            self.connection.execute(translated)
        return None

    def commit(self):
        self.connection.commit()

    def rollback(self):
        self.connection.rollback()

    def close(self):
        self.connection.close()


def is_postgres_url(value: str | None) -> bool:
    text = (value or "").strip().lower()
    return text.startswith("postgres://") or text.startswith("postgresql://")


def normalize_postgres_url(value: str) -> str:
    value = value.strip()
    if value.startswith("postgres://"):
        return "postgresql://" + value[len("postgres://") :]
    return value


def connect_database(database_url: str | None, sqlite_path: str | Path) -> DatabaseConnection:
    if is_postgres_url(database_url):
        if psycopg is None:
            raise RuntimeError(
                "DATABASE_URL apunta a PostgreSQL pero falta psycopg. "
                "Ejecutá: pip install 'psycopg[binary]'"
            )
        connection = psycopg.connect(normalize_postgres_url(database_url), connect_timeout=12)
        return DatabaseConnection(connection, "postgresql")

    path = Path(sqlite_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA busy_timeout = 10000")
    return DatabaseConnection(connection, "sqlite")


def split_sql_script(script: str) -> Iterator[str]:
    """Divide el esquema actual; no contiene procedimientos ni $$ blocks."""
    buffer: list[str] = []
    quote: str | None = None
    for char in script:
        if quote:
            buffer.append(char)
            if char == quote:
                quote = None
            continue
        if char in {"'", '"'}:
            quote = char
            buffer.append(char)
        elif char == ";":
            statement = "".join(buffer).strip()
            if statement:
                yield statement
            buffer = []
        else:
            buffer.append(char)
    statement = "".join(buffer).strip()
    if statement:
        yield statement


def replace_qmark_placeholders(sql: str) -> str:
    """Adapta SQL histórico de SQLite al formato de psycopg.

    Además de convertir ``?`` en ``%s``, duplica cualquier ``%`` que ya
    exista en el SQL. psycopg reserva ese carácter para placeholders, por lo
    que patrones legítimos como ``LIKE '%speed%'`` deben llegar como
    ``LIKE '%%speed%%'``. Al ejecutar la consulta psycopg vuelve a enviarlos
    a PostgreSQL como porcentajes SQL normales.
    """
    output: list[str] = []
    quote: str | None = None
    index = 0
    while index < len(sql):
        char = sql[index]

        # Debe hacerse también dentro de literales SQL: el problema ocurre
        # precisamente con patrones LIKE '%...%'.
        if char == "%":
            output.append("%%")
            index += 1
            continue

        if quote:
            output.append(char)
            if char == quote:
                # SQL escapa comillas duplicándolas.
                if index + 1 < len(sql) and sql[index + 1] == quote:
                    output.append(sql[index + 1])
                    index += 1
                else:
                    quote = None
        elif char in {"'", '"'}:
            quote = char
            output.append(char)
        elif char == "?":
            output.append("%s")
        else:
            output.append(char)
        index += 1
    return "".join(output)


def translate_postgres_sql(sql: str, *, append_returning: bool) -> tuple[str, bool]:
    statement = sql.strip().rstrip(";")
    statement = re.sub(
        r"INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT",
        "BIGSERIAL PRIMARY KEY",
        statement,
        flags=re.IGNORECASE,
    )
    statement = re.sub(r"\bAUTOINCREMENT\b", "", statement, flags=re.IGNORECASE)
    statement = re.sub(
        r"([A-Za-z_][A-Za-z0-9_.]*)\s+COLLATE\s+NOCASE",
        r"lower(\1)",
        statement,
        flags=re.IGNORECASE,
    )
    statement = re.sub(
        r"event_date\s*=\s*date\(opened_at\)",
        "event_date=CAST(CAST(opened_at AS TIMESTAMP) AS DATE)::text",
        statement,
        flags=re.IGNORECASE,
    )
    statement = re.sub(r"\bdate\(([^()]+)\)", r"CAST(\1 AS DATE)", statement, flags=re.IGNORECASE)

    ignored_insert = bool(re.match(r"INSERT\s+OR\s+IGNORE\s+INTO\b", statement, re.IGNORECASE))
    if ignored_insert:
        statement = re.sub(r"INSERT\s+OR\s+IGNORE\s+INTO", "INSERT INTO", statement, count=1, flags=re.IGNORECASE)
        if not re.search(r"\bON\s+CONFLICT\b", statement, re.IGNORECASE):
            statement += " ON CONFLICT DO NOTHING"

    returns_id = False
    insert_match = re.match(r"INSERT\s+INTO\s+([A-Za-z_][A-Za-z0-9_]*)", statement, re.IGNORECASE)
    if append_returning and insert_match and insert_match.group(1).lower() in SERIAL_ID_TABLES:
        if not re.search(r"\bRETURNING\b", statement, re.IGNORECASE):
            statement += " RETURNING id"
        returns_id = True

    return replace_qmark_placeholders(statement), returns_id
