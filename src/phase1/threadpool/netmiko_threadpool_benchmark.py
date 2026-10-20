import csv
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import yaml
from netmiko import ConnectHandler
from netmiko.exceptions import (
    NetmikoAuthenticationException,
    NetmikoTimeoutException,
)

# ---------------------------------------------------------------------
# Project paths
# ---------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[3]

INVENTORY_FILE = (
    PROJECT_ROOT
    / "inventory"
    / "phase1"
    / "devices.yaml"
)

CREDENTIALS_FILE = (
    PROJECT_ROOT
    / "inventory"
    / "phase1"
    / "credentials.yaml"
)


# ---------------------------------------------------------------------
# Benchmark settings
# ---------------------------------------------------------------------

METHOD_NAME = "netmiko_threadpool"
METHOD_FOLDER = "threadpool"
COMMAND = "show running-config"

# Change this value to test scalability:
# 1, 2, 4, 5, 10
MAX_WORKERS = 10


# ---------------------------------------------------------------------
# Run ID
# ---------------------------------------------------------------------

run_id = datetime.now().strftime(
    "%Y%m%d_%H%M%S"
)


# ---------------------------------------------------------------------
# Paths for this specific run
# ---------------------------------------------------------------------

BACKUP_DIR = (
    PROJECT_ROOT
    / "backups"
    / "phase1"
    / METHOD_FOLDER
    / run_id
)

RESULTS_DIR = (
    PROJECT_ROOT
    / "results"
    / "phase1"
    / METHOD_FOLDER
    / run_id
)

RESULTS_FILE = (
    RESULTS_DIR
    / "results.csv"
)


# ---------------------------------------------------------------------
# Prepare directories
# ---------------------------------------------------------------------

BACKUP_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

RESULTS_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


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
        "inventory/phase1/devices.yaml"
    )


if not isinstance(
    credentials,
    dict,
):
    raise RuntimeError(
        "Invalid "
        "inventory/phase1/credentials.yaml"
    )


# ---------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------

def get_device_credentials(
    device_name: str,
) -> dict:
    """
    Return credentials for one device.
    """

    device_credentials = credentials.get(
        device_name
    )

    if not device_credentials:
        raise RuntimeError(
            f"No credentials found for {device_name}"
        )

    username = device_credentials.get(
        "username"
    )

    password = device_credentials.get(
        "password"
    )

    secret = device_credentials.get(
        "secret",
        "",
    )

    if not username or not password:
        raise RuntimeError(
            f"Missing username or password "
            f"for {device_name}"
        )

    return {
        "username": username,
        "password": password,
        "secret": secret,
    }


def save_backup(
    device_name: str,
    config: str,
) -> Path:
    """
    Save one device running configuration inside
    the current run folder.
    """

    backup_file = (
        BACKUP_DIR
        / f"{device_name}.cfg"
    )

    backup_file.write_text(
        config,
        encoding="utf-8",
    )

    return backup_file


def write_results_to_csv(
    results: list[dict],
) -> None:
    """
    Write benchmark results for this run to results.csv.
    """

    fieldnames = [
        "run_id",
        "method",
        "workers",
        "device",
        "host",
        "duration_s",
        "success",
        "bytes",
        "lines",
        "error",
    ]

    with open(
        RESULTS_FILE,
        "w",
        newline="",
        encoding="utf-8",
    ) as csvfile:

        writer = csv.DictWriter(
            csvfile,
            fieldnames=fieldnames,
        )

        writer.writeheader()

        writer.writerows(
            results
        )


def backup_device(
    device: dict,
) -> dict:
    """
    Connect to one device, retrieve show running-config,
    save the backup, and collect benchmark metrics.
    """

    name = device["name"]
    host = device["host"]
    device_type = device["device_type"]

    device_credentials = (
        get_device_credentials(
            name
        )
    )

    connection_params = {
        "device_type": device_type,
        "host": host,
        "username": (
            device_credentials[
                "username"
            ]
        ),
        "password": (
            device_credentials[
                "password"
            ]
        ),
        "secret": (
            device_credentials[
                "secret"
            ]
        ),
    }

    print(
        f"Connecting to {name} ({host})..."
    )

    start_time = time.perf_counter()

    try:

        with ConnectHandler(
            **connection_params
        ) as connection:

            if device_credentials["secret"]:
                connection.enable()

            config = connection.send_command(
                COMMAND
            )

        duration = (
            time.perf_counter()
            - start_time
        )

        backup_file = save_backup(
            name,
            config,
        )

        config_bytes = len(
            config.encode(
                "utf-8"
            )
        )

        config_lines = len(
            config.splitlines()
        )

        print(
            f"{name}: SUCCESS | "
            f"{duration:.3f} s | "
            f"{config_lines} lines | "
            f"{config_bytes} bytes"
        )

        print(
            f"{name}: Saved: "
            f"{backup_file}"
        )

        return {
            "run_id": run_id,
            "method": METHOD_NAME,
            "workers": MAX_WORKERS,
            "device": name,
            "host": host,
            "duration_s": round(
                duration,
                6,
            ),
            "success": True,
            "bytes": config_bytes,
            "lines": config_lines,
            "error": "",
        }

    except (
        NetmikoTimeoutException,
        NetmikoAuthenticationException,
    ) as exc:

        duration = (
            time.perf_counter()
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
            "run_id": run_id,
            "method": METHOD_NAME,
            "workers": MAX_WORKERS,
            "device": name,
            "host": host,
            "duration_s": round(
                duration,
                6,
            ),
            "success": False,
            "bytes": 0,
            "lines": 0,
            "error": str(exc).replace(
                "\n",
                " ",
            ),
        }

    except Exception as exc:

        duration = (
            time.perf_counter()
            - start_time
        )

        print(
            f"{name}: FAILED | "
            f"{duration:.3f} s"
        )

        print(
            f"{name}: Unexpected error: "
            f"{exc}"
        )

        return {
            "run_id": run_id,
            "method": METHOD_NAME,
            "workers": MAX_WORKERS,
            "device": name,
            "host": host,
            "duration_s": round(
                duration,
                6,
            ),
            "success": False,
            "bytes": 0,
            "lines": 0,
            "error": str(exc).replace(
                "\n",
                " ",
            ),
        }


# ---------------------------------------------------------------------
# Main benchmark
# ---------------------------------------------------------------------

def main() -> None:

    print("=" * 70)

    print(
        "Cisco CML Network Automation Benchmark"
    )

    print(
        f"Method : {METHOD_NAME}"
    )

    print(
        f"Devices: {len(devices)}"
    )

    print(
        f"Workers: {MAX_WORKERS}"
    )

    print(
        f"Run ID : {run_id}"
    )

    print("=" * 70)
    print()

    results = []

    batch_start = (
        time.perf_counter()
    )

    with ThreadPoolExecutor(
        max_workers=MAX_WORKERS
    ) as executor:

        future_to_device = {
            executor.submit(
                backup_device,
                device,
            ): device
            for device in devices
        }

        for future in as_completed(
            future_to_device
        ):

            result = future.result()

            results.append(
                result
            )

    batch_duration = (
        time.perf_counter()
        - batch_start
    )

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

    write_results_to_csv(
        results
    )

    successful = sum(
        result["success"]
        for result in results
    )

    failed = (
        len(results)
        - successful
    )

    print()
    print("=" * 70)
    print("Benchmark complete")
    print("=" * 70)

    print(
        f"Method          : "
        f"{METHOD_NAME}"
    )

    print(
        f"Devices         : "
        f"{len(devices)}"
    )

    print(
        f"Workers         : "
        f"{MAX_WORKERS}"
    )

    print(
        f"Successful      : "
        f"{successful}"
    )

    print(
        f"Failed          : "
        f"{failed}"
    )

    print(
        f"Total wall time : "
        f"{batch_duration:.3f} s"
    )

    print(
        f"Run ID          : "
        f"{run_id}"
    )

    print(
        f"Results CSV     : "
        f"{RESULTS_FILE}"
    )

    print(
        f"Backup folder   : "
        f"{BACKUP_DIR}"
    )

    print("=" * 70)


if __name__ == "__main__":
    main()