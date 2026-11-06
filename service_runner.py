from __future__ import annotations

import logging
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: service_runner.py SCRIPT")
    target = (ROOT / sys.argv[1]).resolve()
    if not target.is_file() or target.parent != ROOT:
        raise SystemExit(f"invalid managed script: {target}")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    while True:
        logging.info("Starting %s", target.name)
        process = subprocess.Popen([sys.executable, str(target)], cwd=ROOT)
        exit_code = process.wait()
        logging.warning("%s exited with code %s; restarting in 5 seconds", target.name, exit_code)
        time.sleep(5)


if __name__ == "__main__":
    main()

