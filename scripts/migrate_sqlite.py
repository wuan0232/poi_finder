import argparse
import sqlite3
import sys
from datetime import datetime
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT_DIR / "poi_finder.db"

TASK_COLUMNS = {
    "center_name": "VARCHAR(255)",
    "center_address": "VARCHAR(500)",
    "keyword": "VARCHAR(100)",
    "types_code": "VARCHAR(20)",
    "radius_m": "INTEGER",
    "center_lng": "REAL",
    "center_lat": "REAL",
}

POI_COLUMNS = {"distance_m": "INTEGER"}


def backup_database(connection: sqlite3.Connection, database_path: Path) -> Path:
    backup_dir = ROOT_DIR / "backups"
    backup_dir.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"{database_path.stem}_before_migration_{stamp}.db"
    with sqlite3.connect(backup_path) as backup:
        connection.backup(backup)
    return backup_path


def existing_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}


def add_missing_columns(
    connection: sqlite3.Connection, table: str, columns: dict[str, str]
) -> list[str]:
    existing = existing_columns(connection, table)
    added: list[str] = []
    for name, data_type in columns.items():
        if name not in existing:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {name} {data_type}")
            added.append(f"{table}.{name}")
    return added


def ensure_unique_index(connection: sqlite3.Connection) -> None:
    duplicate = connection.execute(
        """
        SELECT task_id, provider, source_id, COUNT(*)
        FROM pois
        WHERE source_id IS NOT NULL
        GROUP BY task_id, provider, source_id
        HAVING COUNT(*) > 1
        LIMIT 1
        """
    ).fetchone()
    if duplicate:
        raise RuntimeError(
            "检测到重复 POI，未创建唯一索引。请先处理重复记录："
            f"task_id={duplicate[0]}, provider={duplicate[1]}, source_id={duplicate[2]}"
        )
    connection.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_pois_task_provider_source
        ON pois(task_id, provider, source_id)
        WHERE source_id IS NOT NULL
        """
    )


def migrate(database_path: Path) -> None:
    if not database_path.exists():
        raise FileNotFoundError(f"数据库不存在：{database_path}")

    with sqlite3.connect(database_path, timeout=30) as connection:
        backup_path = backup_database(connection, database_path)
        connection.execute("PRAGMA busy_timeout = 30000")
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        added = add_missing_columns(connection, "tasks", TASK_COLUMNS)
        added.extend(add_missing_columns(connection, "pois", POI_COLUMNS))
        ensure_unique_index(connection)
        connection.commit()

    print(f"备份：{backup_path}")
    print("新增字段：" + (", ".join(added) if added else "无"))
    print("SQLite 迁移完成，WAL 和唯一索引已启用。")


def main() -> None:
    parser = argparse.ArgumentParser(description="兼容迁移 POI Finder SQLite 数据库")
    parser.add_argument("database", nargs="?", type=Path, default=DEFAULT_DB)
    args = parser.parse_args()
    try:
        migrate(args.database.resolve())
    except Exception as exc:
        print(f"迁移失败：{exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
