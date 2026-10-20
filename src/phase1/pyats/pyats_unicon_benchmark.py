import csv
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import yaml
from pyats.topology import loader

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

METHOD_NAME = "pyats_unicon"
METHOD_FOLDER = "pyats"
COMMAND = "show running-config"

# Change this value to test scalability:
# 1, 2, 4, 5, 10
MAX_WORKERS = 10


# ---------------------------------------------------------------------
# Run ID
# ---------------------------------------------------------------------

run_id = datetime.now().strftime("%Y%m%d_%H%M%S")


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

RESULTS_FILE = RESULTS_DIR / "results.csv"


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
    raise RuntimeError(  # noqa: TRY004
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
            f"Missing username or password for {device_name}"
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
        writer.writerows(results)


def build_testbed_data() -> dict:
    """
    Build an in-memory pyATS testbed from devices.yaml
    and credentials.yaml.
    """

    testbed_devices = {}

    for device in devices:

        name = device["name"]
        host = device["host"]

        device_credentials = (
            get_device_credentials(name)
        )

        testbed_devices[name] = {
            "os": "ios",
            "platform": "iosv",
            "type": "router",

            "credentials": {
                "default": {
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
                },

                "enable": {
                    "password": (
                        device_credentials[
                            "secret"
                        ]
                    ),
                },
            },

            "connections": {
                "cli": {
                    "protocol": "ssh",
                    "ip": host,

                    # Legacy SSH compatibility required by
                    # the IOSv image used in this CML lab.
                    #
                    # Lab compatibility only.
                    "ssh_options": (
                        "-o KexAlgorithms="
                        "+diffie-hellman-group14-sha1 "
                        "-o KexAlgorithms="
                        "+diffie-hellman-group-exchange-sha1 "
                        "-o HostKeyAlgorithms="
                        "+ssh-rsa"
                    ),

                    # Disable Unicon's default disconnect waits
                    # so they do not dominate benchmark timing.
                    "settings": {
                        "GRACEFUL_DISCONNECT_WAIT_SEC": 0,
                        "POST_DISCONNECT_WAIT_SEC": 0,
                    },
                },
            },
        }

    return {
        "testbed": {
            "name": "cml-benchmark",
        },
        "devices": testbed_devices,
    }


# ---------------------------------------------------------------------
# Build pyATS testbed
# ---------------------------------------------------------------------

testbed_data = build_testbed_data()

testbed = loader.load(
    testbed_data
)

print(
    "pyATS devices:",
    list(testbed.devices.keys())
)

# ---------------------------------------------------------------------
# Device backup worker
# ---------------------------------------------------------------------

def backup_device(
    device_info: dict,
) -> dict:
    """
    Connect to one device using pyATS + Unicon,
    retrieve show running-config,
    save the configuration, and return benchmark metrics.
    """

    name = device_info["name"]
    host = device_info["host"]

    device = testbed.devices[name]

    print(
        f"Connecting to {name} ({host})..."
    )

    start_time = time.perf_counter()

    try:

        # ---------------------------------------------------------
        # Connect
        #
        # Important:
        #
        # init_config_commands=[]
        # prevents Unicon from modifying the router configuration
        # with commands such as:
        #
        #   no logging console
        #   exec-timeout 0
        #
        # We only keep terminal length/width commands to avoid
        # pagination during show running-config.
        # ---------------------------------------------------------

        device.connect(
            via="cli",
            learn_hostname=False,
            log_stdout=False,

            init_exec_commands=[
                "term length 0",
                "term width 0",
            ],

            init_config_commands=[],
        )

        # ---------------------------------------------------------
        # Execute benchmark command
        # ---------------------------------------------------------

        config = device.execute(
            COMMAND
        )

        # ---------------------------------------------------------
        # Disconnect
        # ---------------------------------------------------------

        device.disconnect()

        duration = (
            time.perf_counter()
            - start_time
        )

        # ---------------------------------------------------------
        # Save backup
        # ---------------------------------------------------------

        backup_file = save_backup(
            name,
            config,
        )

        config_bytes = len(
            config.encode("utf-8")
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

    except Exception as exc:

        duration = (
            time.perf_counter()
            - start_time
        )

        # ---------------------------------------------------------
        # Try to disconnect cleanly if the session partially opened
        # ---------------------------------------------------------

        try:
            if device.is_connected():
                device.disconnect()

        except Exception:
            pass

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
        f"Workers : {MAX_WORKERS}"
    )
    print(
        f"Run ID  : {run_id}"
    )
    print("=" * 70)
    print()

    results = []

    # -------------------------------------------------------------
    # Total wall-clock timer
    # -------------------------------------------------------------

    batch_start = (
        time.perf_counter()
    )

    # -------------------------------------------------------------
    # Thread pool
    # -------------------------------------------------------------

    with ThreadPoolExecutor(
        max_workers=MAX_WORKERS
    ) as executor:

        future_to_device = {}

        for device in devices:

            future = executor.submit(
                backup_device,
                device,
            )

            future_to_device[
                future
            ] = device

        # ---------------------------------------------------------
        # Collect results as devices finish
        # ---------------------------------------------------------

        for future in as_completed(
            future_to_device
        ):

            device_info = (
                future_to_device[
                    future
                ]
            )

            try:

                result = future.result()

            except Exception as exc:

                name = device_info[
                    "name"
                ]

                host = device_info[
                    "host"
                ]

                print(
                    f"{name}: Worker exception: "
                    f"{exc}"
                )

                result = {
                    "run_id": run_id,
                    "method": METHOD_NAME,
                    "workers": MAX_WORKERS,
                    "device": name,
                    "host": host,
                    "duration_s": 0,
                    "success": False,
                    "bytes": 0,
                    "lines": 0,
                    "error": str(exc).replace(
                        "\n",
                        " ",
                    ),
                }

            results.append(
                result
            )

    # -------------------------------------------------------------
    # Stop total timer
    # -------------------------------------------------------------

    batch_duration = (
        time.perf_counter()
        - batch_start
    )

    # -------------------------------------------------------------
    # Sort results according to inventory order
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
    # Write CSV
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

    # -------------------------------------------------------------
    # Final summary
    # -------------------------------------------------------------

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