import argparse
import csv
import json
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from time import perf_counter

import requests
import urllib3
import yaml

# ---------------------------------------------------------------------
# Disable warning caused by IOS XE self-signed HTTPS certificates
# ---------------------------------------------------------------------

urllib3.disable_warnings(
    urllib3.exceptions.InsecureRequestWarning
)


# ---------------------------------------------------------------------
# Project paths
# ---------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[3]

INVENTORY_FILE = (
    PROJECT_ROOT
    / "inventory"
    / "phase2"
    / "devices.yaml"
)

CREDENTIALS_FILE = (
    PROJECT_ROOT
    / "inventory"
    / "phase2"
    / "credentials.yaml"
)

BACKUP_ROOT = (
    PROJECT_ROOT
    / "backups"
    / "phase2"
    / "restconf"
)

RESULTS_ROOT = (
    PROJECT_ROOT
    / "results"
    / "phase2"
    / "restconf"
)


# ---------------------------------------------------------------------
# Benchmark configuration
# ---------------------------------------------------------------------

METHOD_NAME = "restconf"

DEFAULT_WORKER_COUNTS = [
    1,
    2,
    4,
]

RESTCONF_PORT = 443
REQUEST_TIMEOUT = 30

RESTCONF_PATH = (
    "/restconf/data/"
    "Cisco-IOS-XE-native:native"
)

HEADERS = {
    "Accept": (
        "application/"
        "yang-data+json"
    )
}


# ---------------------------------------------------------------------
# Load inventory and credentials
# ---------------------------------------------------------------------

with open(
    INVENTORY_FILE,
    "r",
    encoding="utf-8",
) as file:
    inventory = yaml.safe_load(file)


with open(
    CREDENTIALS_FILE,
    "r",
    encoding="utf-8",
) as file:
    credentials = yaml.safe_load(file)


devices = inventory.get(
    "devices",
    [],
)


if not devices:
    raise RuntimeError(
        "No devices found in "
        "inventory/phase2/devices.yaml"
    )


if not isinstance(
    credentials,
    dict,
):
    raise RuntimeError(
        "Invalid "
        "inventory/phase2/credentials.yaml"
    )


# ---------------------------------------------------------------------
# Command-line arguments
# ---------------------------------------------------------------------

def parse_arguments() -> argparse.Namespace:

    parser = argparse.ArgumentParser(
        description=(
            "Phase 2 RESTCONF configuration "
            "backup benchmark."
        )
    )

    parser.add_argument(
        "--workers",
        default="all",
        choices=[
            "1",
            "2",
            "4",
            "all",
        ],
        help=(
            "Number of concurrent workers. "
            "Use 'all' to test 1, 2, and 4."
        ),
    )

    parser.add_argument(
        "--runs",
        type=int,
        default=1,
        help=(
            "Number of repetitions for each "
            "worker count."
        ),
    )

    args = parser.parse_args()

    if args.runs < 1:
        parser.error(
            "--runs must be at least 1."
        )

    return args


# ---------------------------------------------------------------------
# Credential helper
# ---------------------------------------------------------------------

def get_device_credentials(
    device_name: str,
) -> dict:

    device_credentials = credentials.get(
        device_name
    )

    if not device_credentials:
        raise RuntimeError(
            f"No credentials found for "
            f"{device_name}"
        )

    username = device_credentials.get(
        "username"
    )

    password = device_credentials.get(
        "password"
    )

    if not username or not password:
        raise RuntimeError(
            f"Missing username or password "
            f"for {device_name}"
        )

    return {
        "username": username,
        "password": password,
    }


# ---------------------------------------------------------------------
# Device backup worker
# ---------------------------------------------------------------------

def backup_device(
    device: dict,
    backup_dir: Path,
) -> dict:

    name = device["name"]
    host = device["host"]

    device_credentials = (
        get_device_credentials(
            name
        )
    )

    username = (
        device_credentials[
            "username"
        ]
    )

    password = (
        device_credentials[
            "password"
        ]
    )

    url = (
        f"https://{host}:"
        f"{RESTCONF_PORT}"
        f"{RESTCONF_PATH}"
    )

    print(
        f"Requesting {name} "
        f"({host}:{RESTCONF_PORT})..."
    )

    start_time = perf_counter()

    try:

        response = requests.get(
            url,
            auth=(
                username,
                password,
            ),
            headers=HEADERS,
            verify=False,
            timeout=REQUEST_TIMEOUT,
        )

        duration = (
            perf_counter()
            - start_time
        )

        response.raise_for_status()

        # -------------------------------------------------------------
        # Raw HTTP response body
        # -------------------------------------------------------------

        raw_body = response.content

        raw_json_bytes = len(
            raw_body
        )

        # -------------------------------------------------------------
        # Parse YANG-modeled JSON
        # -------------------------------------------------------------

        data = response.json()

        native_key = (
            "Cisco-IOS-XE-native:"
            "native"
        )

        if native_key not in data:
            raise RuntimeError(
                "Cisco-IOS-XE-native:native "
                "data not found in RESTCONF response."
            )

        native_data = data[
            native_key
        ]

        # -------------------------------------------------------------
        # Serialize native subtree consistently
        # -------------------------------------------------------------

        native_json = json.dumps(
            {
                native_key: native_data
            },
            indent=2,
            ensure_ascii=False,
        )

        native_json_bytes = len(
            native_json.encode(
                "utf-8"
            )
        )

        native_json_lines = len(
            native_json.splitlines()
        )

        # -------------------------------------------------------------
        # Save JSON backup
        # -------------------------------------------------------------

        backup_file = (
            backup_dir
            / f"{name}.json"
        )

        backup_file.write_text(
            native_json,
            encoding="utf-8",
        )

        print(
            f"{name}: SUCCESS | "
            f"{duration:.3f} s | "
            f"{native_json_lines} lines | "
            f"native JSON {native_json_bytes} bytes | "
            f"raw HTTP body {raw_json_bytes} bytes"
        )

        print(
            f"{name}: Saved: "
            f"{backup_file}"
        )

        return {
            "device": name,
            "host": host,
            "duration_s": duration,
            "success": True,
            "native_json_bytes": (
                native_json_bytes
            ),
            "raw_body_bytes": (
                raw_json_bytes
            ),
            "lines": (
                native_json_lines
            ),
            "http_status": (
                response.status_code
            ),
            "error": "",
        }

    except Exception as exc:

        duration = (
            perf_counter()
            - start_time
        )

        print(
            f"{name}: FAILED | "
            f"{duration:.3f} s"
        )

        print(
            f"{name}: Error: {exc}"
        )

        return {
            "device": name,
            "host": host,
            "duration_s": duration,
            "success": False,
            "native_json_bytes": 0,
            "raw_body_bytes": 0,
            "lines": 0,
            "http_status": 0,
            "error": str(exc).replace(
                "\n",
                " ",
            ),
        }


# ---------------------------------------------------------------------
# CSV helper
# ---------------------------------------------------------------------

def write_results_to_csv(
    csv_file: Path,
    run_id: str,
    workers: int,
    repetition: int,
    results: list[dict],
) -> None:

    fieldnames = [
        "run_id",
        "method",
        "workers",
        "repetition",
        "device",
        "host",
        "duration_s",
        "success",
        "http_status",
        "native_json_bytes",
        "raw_body_bytes",
        "lines",
        "error",
    ]

    with open(
        csv_file,
        "w",
        newline="",
        encoding="utf-8",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )

        writer.writeheader()

        for result in results:

            writer.writerow({
                "run_id": run_id,
                "method": METHOD_NAME,
                "workers": workers,
                "repetition": repetition,
                "device": result["device"],
                "host": result["host"],
                "duration_s": (
                    f"{result['duration_s']:.6f}"
                ),
                "success": (
                    result["success"]
                ),
                "http_status": (
                    result[
                        "http_status"
                    ]
                ),
                "native_json_bytes": (
                    result[
                        "native_json_bytes"
                    ]
                ),
                "raw_body_bytes": (
                    result[
                        "raw_body_bytes"
                    ]
                ),
                "lines": (
                    result["lines"]
                ),
                "error": (
                    result["error"]
                ),
            })


# ---------------------------------------------------------------------
# Run one benchmark
# ---------------------------------------------------------------------

def run_benchmark(
    workers: int,
    repetition: int,
) -> dict:

    run_id = datetime.now().strftime(
        "%Y%m%d_%H%M%S_%f"
    )

    backup_dir = (
        BACKUP_ROOT
        / run_id
    )

    results_dir = (
        RESULTS_ROOT
        / run_id
    )

    backup_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    results_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    csv_file = (
        results_dir
        / "results.csv"
    )

    print()
    print("=" * 70)
    print(
        "Phase 2 RESTCONF Benchmark"
    )
    print("=" * 70)

    print(
        f"Devices    : {len(devices)}"
    )

    print(
        f"Workers    : {workers}"
    )

    print(
        f"Repetition : {repetition}"
    )

    print(
        f"RESTCONF   : HTTPS/{RESTCONF_PORT}"
    )

    print(
        f"Run ID     : {run_id}"
    )

    print("=" * 70)
    print()

    benchmark_start = (
        perf_counter()
    )

    results = []

    with ThreadPoolExecutor(
        max_workers=workers
    ) as executor:

        future_to_device = {
            executor.submit(
                backup_device,
                device,
                backup_dir,
            ): device
            for device in devices
        }

        for future in as_completed(
            future_to_device
        ):

            device = (
                future_to_device[
                    future
                ]
            )

            try:

                result = (
                    future.result()
                )

            except Exception as exc:

                result = {
                    "device": (
                        device["name"]
                    ),
                    "host": (
                        device["host"]
                    ),
                    "duration_s": 0,
                    "success": False,
                    "native_json_bytes": 0,
                    "raw_body_bytes": 0,
                    "lines": 0,
                    "http_status": 0,
                    "error": (
                        str(exc)
                        .replace(
                            "\n",
                            " ",
                        )
                    ),
                }

            results.append(
                result
            )

    wall_clock = (
        perf_counter()
        - benchmark_start
    )

    # -------------------------------------------------------------
    # Preserve inventory order
    # -------------------------------------------------------------

    device_order = {
        device["name"]: index
        for index, device
        in enumerate(devices)
    }

    results.sort(
        key=lambda result: (
            device_order[
                result["device"]
            ]
        )
    )

    # -------------------------------------------------------------
    # Save CSV
    # -------------------------------------------------------------

    write_results_to_csv(
        csv_file=csv_file,
        run_id=run_id,
        workers=workers,
        repetition=repetition,
        results=results,
    )

    # -------------------------------------------------------------
    # Summary
    # -------------------------------------------------------------

    successful = sum(
        result["success"]
        for result in results
    )

    failed = (
        len(results)
        - successful
    )

    total_native_json_bytes = sum(
        result["native_json_bytes"]
        for result in results
        if result["success"]
    )

    total_raw_body_bytes = sum(
        result["raw_body_bytes"]
        for result in results
        if result["success"]
    )

    total_lines = sum(
        result["lines"]
        for result in results
        if result["success"]
    )

    print()
    print("=" * 70)
    print("Benchmark complete")
    print("=" * 70)

    print(
        f"Method                  : "
        f"{METHOD_NAME}"
    )

    print(
        f"Devices                 : "
        f"{len(devices)}"
    )

    print(
        f"Workers                 : "
        f"{workers}"
    )

    print(
        f"Repetition              : "
        f"{repetition}"
    )

    print(
        f"Successful              : "
        f"{successful}"
    )

    print(
        f"Failed                  : "
        f"{failed}"
    )

    print(
        f"Total wall time         : "
        f"{wall_clock:.3f} s"
    )

    print(
        f"Native JSON bytes total : "
        f"{total_native_json_bytes}"
    )

    print(
        f"Raw HTTP body bytes     : "
        f"{total_raw_body_bytes}"
    )

    print(
        f"Native JSON lines total : "
        f"{total_lines}"
    )

    print(
        f"Run ID                  : "
        f"{run_id}"
    )

    print(
        f"Results CSV             : "
        f"{csv_file}"
    )

    print(
        f"Backup folder           : "
        f"{backup_dir}"
    )

    print("=" * 70)

    return {
        "workers": workers,
        "repetition": repetition,
        "wall_clock": wall_clock,
        "successful": successful,
        "failed": failed,
        "run_id": run_id,
    }


# ---------------------------------------------------------------------
# Aggregate summary
# ---------------------------------------------------------------------

def print_aggregate_summary(
    benchmark_runs: list[dict],
) -> None:

    print()
    print()
    print("=" * 78)
    print(
        "RESTCONF Aggregate Summary"
    )
    print("=" * 78)

    worker_values = sorted(
        {
            run["workers"]
            for run in benchmark_runs
        }
    )

    averages = {}

    print(
        f"{'Workers':<10}"
        f"{'Runs':<8}"
        f"{'Average':<12}"
        f"{'Median':<12}"
        f"{'Std Dev':<12}"
        f"{'Min':<12}"
        f"{'Max':<12}"
    )

    print("-" * 78)

    for workers in worker_values:

        wall_times = [
            run["wall_clock"]
            for run in benchmark_runs
            if run["workers"] == workers
        ]

        average = (
            statistics.mean(
                wall_times
            )
        )

        median = (
            statistics.median(
                wall_times
            )
        )

        if len(wall_times) > 1:

            std_dev = (
                statistics.stdev(
                    wall_times
                )
            )

        else:

            std_dev = 0.0

        minimum = min(
            wall_times
        )

        maximum = max(
            wall_times
        )

        averages[
            workers
        ] = average

        print(
            f"{workers:<10}"
            f"{len(wall_times):<8}"
            f"{average:<12.3f}"
            f"{median:<12.3f}"
            f"{std_dev:<12.3f}"
            f"{minimum:<12.3f}"
            f"{maximum:<12.3f}"
        )

    # -------------------------------------------------------------
    # Scaling summary
    # -------------------------------------------------------------

    if 1 in averages:

        baseline = averages[1]

        print()
        print("=" * 78)
        print(
            "Scaling relative to 1 worker"
        )
        print("=" * 78)

        print(
            f"{'Workers':<10}"
            f"{'Avg Time':<15}"
            f"{'Speedup':<15}"
            f"{'Efficiency':<15}"
        )

        print("-" * 55)

        for workers in worker_values:

            average = (
                averages[
                    workers
                ]
            )

            speedup = (
                baseline
                / average
            )

            efficiency = (
                speedup
                / workers
                * 100
            )

            print(
                f"{workers:<10}"
                f"{average:<15.3f}"
                f"{speedup:<15.2f}"
                f"{efficiency:<14.1f}%"
            )

    print("=" * 78)


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

def main() -> None:

    args = parse_arguments()

    if args.workers == "all":

        worker_counts = (
            DEFAULT_WORKER_COUNTS
        )

    else:

        worker_counts = [
            int(
                args.workers
            )
        ]

    print()
    print("=" * 70)

    print(
        "Phase 2 - RESTCONF "
        "Configuration Backup Benchmark"
    )

    print("=" * 70)

    print(
        f"Devices : {len(devices)}"
    )

    print(
        f"Workers : {worker_counts}"
    )

    print(
        f"Runs    : {args.runs}"
    )

    benchmark_runs = []

    for workers in worker_counts:

        for repetition in range(
            1,
            args.runs + 1,
        ):

            benchmark_result = (
                run_benchmark(
                    workers=workers,
                    repetition=repetition,
                )
            )

            benchmark_runs.append(
                benchmark_result
            )

    print_aggregate_summary(
        benchmark_runs
    )


if __name__ == "__main__":
    main()

# Usage:

# python .\src\phase2\restconf\restconf_benchmark.py --workers all --runs 1
# python .\src\phase2\restconf\restconf_benchmark.py --workers all --runs 3