import csv
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import yaml
from lxml import etree
from ncclient import manager

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

METHOD_NAME = "netconf_ncclient"
METHOD_FOLDER = "netconf"

# Change this value for scalability tests:
# 1, 2, 4, 5, 10
MAX_WORKERS = 10

# This IOSv implementation exposes legacy NETCONF through
# the SSH subsystem on TCP/22 rather than NETCONF/YANG on TCP/830.
NETCONF_PORT = 22

CONNECTION_TIMEOUT = 15


# ---------------------------------------------------------------------
# Run ID
# ---------------------------------------------------------------------

run_id = datetime.now().strftime("%Y%m%d_%H%M%S")


# ---------------------------------------------------------------------
# Paths for this run
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
# Load inventory
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
# Credentials helper
# ---------------------------------------------------------------------

def get_device_credentials(
    device_name: str,
) -> dict:

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

    if not username or not password:
        raise RuntimeError(
            f"Missing username or password for {device_name}"
        )

    return {
        "username": username,
        "password": password,
    }


# ---------------------------------------------------------------------
# NETCONF XML helper
# ---------------------------------------------------------------------

def extract_cli_config(
    xml_response: str,
) -> str:
    """
    Extract the IOS CLI configuration from:

        <cli-config-data-block>
            ...
        </cli-config-data-block>

    The IOSv image used by this lab implements legacy NETCONF and
    returns traditional IOS CLI configuration text inside this XML
    element rather than YANG-modeled configuration data.
    """

    root = etree.fromstring(
        xml_response.encode("utf-8")
    )

    elements = root.xpath(
        "//*[local-name()='cli-config-data-block']"
    )

    if not elements:
        raise RuntimeError(
            "NETCONF response did not contain "
            "<cli-config-data-block>"
        )

    config = elements[0].text

    if config is None:
        raise RuntimeError(
            "<cli-config-data-block> was empty"
        )

    # Remove only XML formatting newline(s) surrounding the
    # configuration while preserving the configuration itself.
    config = config.strip("\r\n")

    return config


# ---------------------------------------------------------------------
# Backup helper
# ---------------------------------------------------------------------

def save_backup(
    device_name: str,
    config: str,
) -> Path:

    backup_file = (
        BACKUP_DIR
        / f"{device_name}.cfg"
    )

    backup_file.write_text(
        config,
        encoding="utf-8",
    )

    return backup_file


# ---------------------------------------------------------------------
# CSV helper
# ---------------------------------------------------------------------

def write_results_to_csv(
    results: list[dict],
) -> None:

    fieldnames = [
        "run_id",
        "method",
        "workers",
        "device",
        "host",
        "duration_s",
        "success",
        "bytes",
        "raw_xml_bytes",
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


# ---------------------------------------------------------------------
# Device worker
# ---------------------------------------------------------------------

def backup_device(
    device_info: dict,
) -> dict:
    """
    Connect to one IOSv device using NETCONF over SSH,
    retrieve the running configuration with <get-config>,
    extract the CLI configuration text, save it, and
    return benchmark metrics.
    """

    name = device_info["name"]
    host = device_info["host"]

    device_credentials = (
        get_device_credentials(name)
    )

    username = (
        device_credentials["username"]
    )

    password = (
        device_credentials["password"]
    )

    print(
        f"Connecting to {name} "
        f"({host}:{NETCONF_PORT})..."
    )

    start_time = time.perf_counter()

    connection = None

    try:

        # ---------------------------------------------------------
        # NETCONF session
        # ---------------------------------------------------------

        connection = manager.connect(
            host=host,
            port=NETCONF_PORT,

            username=username,
            password=password,

            hostkey_verify=False,

            allow_agent=False,
            look_for_keys=False,

            timeout=CONNECTION_TIMEOUT,
        )

        # ---------------------------------------------------------
        # Retrieve running configuration
        # ---------------------------------------------------------

        response = connection.get_config(
            source="running"
        )

        raw_xml = response.xml

        # ---------------------------------------------------------
        # Extract CLI configuration from legacy IOS NETCONF reply
        # ---------------------------------------------------------

        config = extract_cli_config(
            raw_xml
        )

        # ---------------------------------------------------------
        # Close NETCONF session
        # ---------------------------------------------------------

        connection.close_session()

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

        raw_xml_bytes = len(
            raw_xml.encode("utf-8")
        )

        config_lines = len(
            config.splitlines()
        )

        print(
            f"{name}: SUCCESS | "
            f"{duration:.3f} s | "
            f"{config_lines} lines | "
            f"{config_bytes} bytes | "
            f"XML {raw_xml_bytes} bytes"
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
            "raw_xml_bytes": raw_xml_bytes,
            "lines": config_lines,
            "error": "",
        }

    except Exception as exc:

        duration = (
            time.perf_counter()
            - start_time
        )

        # ---------------------------------------------------------
        # Try to close partially established NETCONF session
        # ---------------------------------------------------------

        if connection is not None:
            try:
                connection.close_session()
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
            "raw_xml_bytes": 0,
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
        f"NETCONF : SSH/{NETCONF_PORT}"
    )

    print(
        f"Run ID  : {run_id}"
    )

    print("=" * 70)
    print()

    results = []

    # -------------------------------------------------------------
    # Total batch wall-clock timer
    # -------------------------------------------------------------

    batch_start = (
        time.perf_counter()
    )

    # -------------------------------------------------------------
    # ThreadPoolExecutor
    # -------------------------------------------------------------

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
                    "raw_xml_bytes": 0,
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
    # Stop total batch timer
    # -------------------------------------------------------------

    batch_duration = (
        time.perf_counter()
        - batch_start
    )

    # -------------------------------------------------------------
    # Sort according to inventory order
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
    # Aggregate data size information
    # -------------------------------------------------------------

    total_config_bytes = sum(
        result["bytes"]
        for result in results
        if result["success"]
    )

    total_xml_bytes = sum(
        result["raw_xml_bytes"]
        for result in results
        if result["success"]
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
        f"Method             : "
        f"{METHOD_NAME}"
    )

    print(
        f"Devices            : "
        f"{len(devices)}"
    )

    print(
        f"Workers            : "
        f"{MAX_WORKERS}"
    )

    print(
        f"Successful         : "
        f"{successful}"
    )

    print(
        f"Failed             : "
        f"{failed}"
    )

    print(
        f"Total wall time    : "
        f"{batch_duration:.3f} s"
    )

    print(
        f"Config bytes total : "
        f"{total_config_bytes}"
    )

    print(
        f"Raw XML bytes total: "
        f"{total_xml_bytes}"
    )

    print(
        f"Run ID             : "
        f"{run_id}"
    )

    print(
        f"Results CSV        : "
        f"{RESULTS_FILE}"
    )

    print(
        f"Backup folder      : "
        f"{BACKUP_DIR}"
    )

    print("=" * 70)


if __name__ == "__main__":
    main()