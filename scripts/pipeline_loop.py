from __future__ import annotations

import os
import subprocess
import time

DEFAULT_CITIES = "深圳,上海,北京,广州,成都,杭州"


def main() -> None:
    while True:
        command = [
            "python",
            "cli.py",
            "run",
            "--city",
            os.getenv("PIPELINE_CITIES", DEFAULT_CITIES),
            "--persona",
            os.getenv("PIPELINE_PERSONA", "worker"),
            "--top",
            os.getenv("PIPELINE_TOP", "10"),
            "--engine",
            "graph",
        ]
        subprocess.run(command, check=False)
        time.sleep(_interval_seconds())


def _interval_seconds() -> int:
    value = os.getenv("PIPELINE_INTERVAL_SECONDS", "86400")
    try:
        return max(1, int(value))
    except ValueError:
        return 86400


if __name__ == "__main__":
    main()
