"""Migra una base SQLite de Floki Manager a PostgreSQL.

Uso:
  python migrate_sqlite_to_postgres.py --sqlite data/floki.db --database-url "$DATABASE_URL"

El destino se reemplaza por completo. Usar sobre una base PostgreSQL nueva.
"""
from __future__ import annotations

import argparse
import os
import secrets
import sqlite3
import sys
from pathlib import Path

from database import connect_database, is_postgres_url

TABLES = [
    "users",
    "cash_sessions",
    "promoters",
    "price_presets",
    "entry_prices",
    "beverage_products",
    "ticketing_products",
    "beverage_stock",
    "birthday_events",
    "promoter_guests",
    "guest_checkins",
    "list_imports",
    "list_workspaces",
    "movements",
    "birthday_benefits",
]
SERIAL_TABLES = [
    "users", "cash_sessions", "promoters", "beverage_products", "ticketing_products",
    "beverage_stock", "birthday_events", "promoter_guests", "guest_checkins",
    "list_imports", "movements", "birthday_benefits",
]


def quote_identifier(value: str) -> str:
    if not value.replace("_", "").isalnum():
        raise ValueError(f"Identificador inválido: {value}")
    return f'"{value}"'


def migrate(sqlite_path: Path, database_url: str, confirm_replace: bool) -> None:
    if not sqlite_path.exists():
        raise FileNotFoundError(f"No existe la base SQLite: {sqlite_path}")
    if not is_postgres_url(database_url):
        raise ValueError("--database-url debe ser una URL PostgreSQL")
    if not confirm_replace:
        raise ValueError("Agregá --replace para confirmar que el PostgreSQL destino puede reemplazarse")

    # Inicializa esquema y migraciones con la propia aplicación.
    os.environ["DATABASE_URL"] = database_url
    os.environ.setdefault("FLOKI_SECRET_KEY", secrets.token_urlsafe(48))
    os.environ["FLOKI_SKIP_AUTO_INIT"] = "1"
    from app import init_db  # import tardío para respetar DATABASE_URL

    init_db()
    source = sqlite3.connect(sqlite_path)
    source.row_factory = sqlite3.Row
    target = connect_database(database_url, sqlite_path)
    try:
        truncate_tables = ", ".join(quote_identifier(table) for table in reversed(TABLES))
        target.execute(f"TRUNCATE TABLE {truncate_tables} RESTART IDENTITY CASCADE")
        target.commit()
        total = 0
        for table in TABLES:
            exists = source.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone()
            if not exists:
                print(f"- {table}: no existe en SQLite, se omite")
                continue
            rows = source.execute(f"SELECT * FROM {quote_identifier(table)}").fetchall()
            if not rows:
                print(f"- {table}: 0 filas")
                continue
            columns = rows[0].keys()
            placeholders = ", ".join("?" for _ in columns)
            column_sql = ", ".join(quote_identifier(column) for column in columns)
            sql = f"INSERT INTO {quote_identifier(table)} ({column_sql}) VALUES ({placeholders})"
            target.executemany(sql, [tuple(row[column] for column in columns) for row in rows])
            target.commit()
            total += len(rows)
            print(f"✓ {table}: {len(rows)} filas")

        for table in SERIAL_TABLES:
            target.execute(
                "SELECT setval(pg_get_serial_sequence(?, 'id'), COALESCE((SELECT MAX(id) FROM "
                + quote_identifier(table)
                + "), 1), (SELECT COUNT(*) > 0 FROM "
                + quote_identifier(table)
                + "))",
                (table,),
            )
        target.commit()
        print(f"\nMigración terminada: {total} registros copiados.")
    except Exception:
        target.rollback()
        raise
    finally:
        source.close()
        target.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrar Floki Manager de SQLite a PostgreSQL")
    parser.add_argument("--sqlite", default="data/floki.db", help="Ruta de la base SQLite")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", ""), help="URL PostgreSQL")
    parser.add_argument("--replace", action="store_true", help="Confirma reemplazar el contenido del destino")
    args = parser.parse_args()
    try:
        migrate(Path(args.sqlite), args.database_url, args.replace)
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
