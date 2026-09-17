import argparse
import sqlite3
from datetime import datetime
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent


def main() -> None:
    parser = argparse.ArgumentParser(description="在线备份 POI Finder SQLite 数据库")
    parser.add_argument("--source", type=Path, default=ROOT_DIR / "poi_finder.db")
    parser.add_argument("--output-dir", type=Path, default=ROOT_DIR / "backups")
    args = parser.parse_args()

    source = args.source.resolve()
    if not source.exists():
        raise SystemExit(f"数据库不存在：{source}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    destination = args.output_dir / f"{source.stem}_{stamp}.db"

    with sqlite3.connect(source, timeout=30) as source_db:
        with sqlite3.connect(destination) as backup_db:
            source_db.backup(backup_db)
    print(f"备份完成：{destination.resolve()}")


if __name__ == "__main__":
    main()
