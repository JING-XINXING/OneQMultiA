"""从热备恢复 SQLite。

用法（项目根目录）：
    python -m oneqmultia.tools.restore_db --list
    python -m oneqmultia.tools.restore_db --file data/backups/oneqmultia_....db
    python -m oneqmultia.tools.restore_db --latest
"""

from __future__ import annotations

import sys

from oneqmultia.storage.backup import list_backups, restore_database
from oneqmultia.storage.database import engine


def main(argv: list[str] | None = None) -> int:
    """命令行入口。返回进程退出码。"""
    args = list(sys.argv[1:] if argv is None else argv)
    backups = list_backups(engine)
    if "--list" in args or not args:
        if not backups:
            print("没有可用热备。")
            return 0
        for path in backups:
            print(path)
        return 0
    if "--latest" in args:
        if not backups:
            print("没有可用热备。", file=sys.stderr)
            return 1
        restore_database(engine, backups[0])
        print(f"已恢复：{backups[0]}")
        return 0
    if "--file" in args:
        idx = args.index("--file")
        if idx + 1 >= len(args):
            print("请在 --file 后提供备份路径。", file=sys.stderr)
            return 2
        restore_database(engine, args[idx + 1])
        print(f"已恢复：{args[idx + 1]}")
        return 0
    print("未知参数。可用 --list / --latest / --file <path>", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
