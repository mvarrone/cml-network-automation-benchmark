import csv
import tempfile
import time
from datetime import datetime
from pathlib import Path

import yaml
from nornir import InitNornir
from nornir.core.task import Result, Task
from nornir_netmiko.connections import CONNECTION_NAME

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

METHOD_NAME = "nornir_netmiko"
METHOD_FOLDER = "nornir"
COMMAND = "show running-config"

# Change this value later to test:
# 1, 2, 4, 5, 10
NUM_WORKERS = 10


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
# Load project inventory
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
    Write benchmark results for this run.
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


def build_nornir_hosts() -> dict:
    """
    Convert devices.yaml + credentials.yaml into
    a Nornir SimpleInventory hosts dictionary.
    """

    hosts = {}

    for device in devices:

        name = device["name"]

        device_credentials = (
            get_device_credentials(
                name
            )
        )

        # devices.yaml currently uses:
        #
        # device_type: cisco_ios
        #
        # Nornir-Netmiko also supports the generic
        # NAPALM-style platform name "ios", which
        # maps internally to Netmiko's cisco_ios.

        platform = (
            "ios"
            if device["device_type"]
            == "cisco_ios"
            else device["device_type"]
        )

        hosts[name] = {
            "hostname": device["host"],

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

            "platform": platform,

            "connection_options": {
                "netmiko": {
                    "extras": {
                        "secret": (
                            device_credentials[
                                "secret"
                            ]
                        )
                    }
                }
            },
        }

    return hosts


def backup_task(
    task: Task,
) -> Result:
    """
    Nornir task executed once per host.

    Nornir's ThreadedRunner controls the concurrency,
    while the nornir-netmiko connection plugin provides
    the Netmiko SSH connection.
    """

    name = task.host.name
    host = task.host.hostname

    print(
        f"Connecting to {name} ({host})..."
    )

    start_time = time.perf_counter()

    try:

        connection = task.host.get_connection(
            CONNECTION_NAME,
            task.nornir.config,
        )

        secret = (
            task.host.connection_options[
                "netmiko"
            ].extras.get(
                "secret",
                "",
            )
        )

        if secret:
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

        benchmark_result = {
            "run_id": run_id,
            "method": METHOD_NAME,
            "workers": NUM_WORKERS,
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

        benchmark_result = {
            "run_id": run_id,
            "method": METHOD_NAME,
            "workers": NUM_WORKERS,
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

    # Store our benchmark data on the host so main()
    # can collect it after the threaded run finishes.

    task.host.data[
        "benchmark_result"
    ] = benchmark_result

    return Result(
        host=task.host,
        result=benchmark_result,
    )


# ---------------------------------------------------------------------
# Main benchmark
# ---------------------------------------------------------------------

def main() -> None:

    print("=" * 70)

    print(
        "Cisco CML Network Automation Benchmark"
    )

    print(
        f"Method  : {METHOD_NAME}"
    )

    print(
        f"Devices : {len(devices)}"
    )

    print(
        f"Workers : {NUM_WORKERS}"
    )

    print(
        f"Run ID  : {run_id}"
    )

    print("=" * 70)
    print()

    nornir_hosts = (
        build_nornir_hosts()
    )

    # -------------------------------------------------------------
    # Temporary native Nornir inventory
    # -------------------------------------------------------------

    with tempfile.TemporaryDirectory() as temp_dir:

        temp_path = Path(
            temp_dir
        )

        hosts_file = (
            temp_path
            / "hosts.yaml"
        )

        groups_file = (
            temp_path
            / "groups.yaml"
        )

        defaults_file = (
            temp_path
            / "defaults.yaml"
        )

        hosts_file.write_text(
            yaml.safe_dump(
                nornir_hosts,
                sort_keys=False,
            ),
            encoding="utf-8",
        )

        groups_file.write_text(
            "{}\n",
            encoding="utf-8",
        )

        defaults_file.write_text(
            "{}\n",
            encoding="utf-8",
        )

        # ---------------------------------------------------------
        # Initialize Nornir
        # ---------------------------------------------------------

        nr = InitNornir(
            inventory={
                "plugin": "SimpleInventory",
                "options": {
                    "host_file": str(
                        hosts_file
                    ),
                    "group_file": str(
                        groups_file
                    ),
                    "defaults_file": str(
                        defaults_file
                    ),
                },
            },

            runner={
                "plugin": "threaded",
                "options": {
                    "num_workers": (
                        NUM_WORKERS
                    )
                },
            },

            logging={
                "enabled": False,
            },
        )

        # ---------------------------------------------------------
        # Benchmark
        # ---------------------------------------------------------

        batch_start = (
            time.perf_counter()
        )

        nr.run(
            task=backup_task
        )

        batch_duration = (
            time.perf_counter()
            - batch_start
        )

        # ---------------------------------------------------------
        # Collect benchmark results
        # ---------------------------------------------------------

        results = []

        for device in devices:

            name = device["name"]

            benchmark_result = (
                nr.inventory.hosts[
                    name
                ].data.get(
                    "benchmark_result"
                )
            )

            if benchmark_result:
                results.append(
                    benchmark_result
                )

        nr.close_connections()

    # -------------------------------------------------------------
    # Write results
    # -------------------------------------------------------------

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

    print(
        "Benchmark complete"
    )

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
        f"{NUM_WORKERS}"
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