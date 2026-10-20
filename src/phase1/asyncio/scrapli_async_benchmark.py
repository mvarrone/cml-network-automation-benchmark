import asyncio
import csv
import time
from datetime import datetime
from pathlib import Path

import yaml
from scrapli import AsyncScrapli

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

METHOD_NAME = "scrapli_asyncio"
METHOD_FOLDER = "asyncio"
COMMAND = "show running-config"

# Change this later to test:
# 1, 2, 4, 5, 10
MAX_CONCURRENT = 10


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
# Async concurrency limiter
# ---------------------------------------------------------------------

semaphore = asyncio.Semaphore(
    MAX_CONCURRENT
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
            f"No credentials found for "
            f"{device_name}"
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
        "max_concurrent",
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
        writer.writerows(results)


async def backup_device(
    device: dict,
) -> dict:
    """
    Connect asynchronously to one device, retrieve show running-config,
    save the backup, and collect benchmark metrics.
    """

    name = device["name"]
    host = device["host"]

    device_credentials = (
        get_device_credentials(
            name
        )
    )

    connection_params = {
        "host": host,
        "auth_username": (
            device_credentials[
                "username"
            ]
        ),
        "auth_password": (
            device_credentials[
                "password"
            ]
        ),
        "auth_secondary": (
            device_credentials[
                "secret"
            ]
        ),
        "auth_strict_key": False,
        "platform": "cisco_iosxe",
        "transport": "asyncssh",

        # Legacy SSH compatibility for IOSv.
        # Lab compatibility only; do not enable SHA-1 algorithms
        # on production infrastructure unless explicitly required.
        "transport_options": {
            "asyncssh": {
                "known_hosts": None,
                "client_keys": None,
                "kex_algs": [
                    (
                        "diffie-hellman-"
                        "group14-sha1"
                    ),
                    (
                        "diffie-hellman-"
                        "group-exchange-sha1"
                    ),
                ],
                "server_host_key_algs": [
                    "ssh-rsa",
                ],
            }
        },
    }

    async with semaphore:

        print(
            f"Connecting to "
            f"{name} ({host})..."
        )

        start_time = (
            time.perf_counter()
        )

        try:

            async with AsyncScrapli(
                **connection_params
            ) as connection:

                response = (
                    await connection.send_command(
                        COMMAND
                    )
                )

                config = response.result

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
                "max_concurrent": (
                    MAX_CONCURRENT
                ),
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
                f"{name}: Error: {exc}"
            )

            return {
                "run_id": run_id,
                "method": METHOD_NAME,
                "max_concurrent": (
                    MAX_CONCURRENT
                ),
                "device": name,
                "host": host,
                "duration_s": round(
                    duration,
                    6,
                ),
                "success": False,
                "bytes": 0,
                "lines": 0,
                "error": (
                    str(exc)
                    .replace(
                        "\n",
                        " ",
                    )
                ),
            }


# ---------------------------------------------------------------------
# Main benchmark
# ---------------------------------------------------------------------

async def main() -> None:

    print("=" * 70)
    print(
        "Cisco CML Network "
        "Automation Benchmark"
    )

    print(
        f"Method         : "
        f"{METHOD_NAME}"
    )

    print(
        f"Devices        : "
        f"{len(devices)}"
    )

    print(
        f"Max concurrent : "
        f"{MAX_CONCURRENT}"
    )

    print(
        f"Run ID         : "
        f"{run_id}"
    )

    print("=" * 70)
    print()

    batch_start = (
        time.perf_counter()
    )

    tasks = [
        backup_device(
            device
        )
        for device in devices
    ]

    results = await asyncio.gather(
        *tasks
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
        f"Max concurrent  : "
        f"{MAX_CONCURRENT}"
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
    asyncio.run(
        main()
    )