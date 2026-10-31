from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _run(command: list[str]) -> None:
    print("+ " + " ".join(command), flush=True)
    subprocess.run(command, cwd=PROJECT_ROOT, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the full experiment pipeline.")
    parser.add_argument("--demo", action="store_true", help="Use a synthetic CI fixture.")
    parser.add_argument("--rows", type=int, default=30_000)
    parser.add_argument("--bootstrap-reps", type=int, default=1_000)
    parser.add_argument("--target", choices=["local", "bigquery"], default="local")
    args = parser.parse_args()
    if args.target == "bigquery":
        os.environ.setdefault(
            "GOOGLE_CLOUD_PROJECT",
            os.environ.get("GCP_PROJECT_ID", "music-promotion-experiment-lab"),
        )

    if not args.demo:
        _run([sys.executable, "scripts/download_lastfm.py"])

    build_command = [
        sys.executable,
        "scripts/build_experiment.py",
        "--rows",
        str(args.rows),
    ]
    if args.demo:
        build_command.append("--demo")
    _run(build_command)

    local_dbt = Path(sys.executable).with_name("dbt.exe")
    dbt_executable = str(local_dbt) if local_dbt.exists() else shutil.which("dbt")
    if not dbt_executable:
        raise RuntimeError("dbt is not installed in the active Python environment.")
    for command in ("seed", "run", "test"):
        flags = ["--full-refresh"] if command == "seed" else []
        _run([dbt_executable, command, "--profiles-dir", ".", "--target", args.target, *flags])

    _run(
        [
            sys.executable,
            "scripts/analyze_experiment.py",
            "--bootstrap-reps",
            str(args.bootstrap_reps),
            "--target",
            args.target,
        ]
    )
    _run([sys.executable, "-m", "pytest"])
    print("Pipeline complete. Open docs/index.html and reports/decision_memo.md.")


if __name__ == "__main__":
    main()
