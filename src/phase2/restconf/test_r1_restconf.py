from pathlib import Path

import requests
import urllib3
import yaml

# ---------------------------------------------------------------------
# Disable warning caused by the IOS XE self-signed HTTPS certificate
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


# ---------------------------------------------------------------------
# Phase 2 R1
# ---------------------------------------------------------------------

DEVICE_NAME = "R1"
PORT = 443


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


r1 = next(
    (
        device
        for device in devices
        if device.get("name") == DEVICE_NAME
    ),
    None,
)


if r1 is None:
    raise RuntimeError(
        f"{DEVICE_NAME} was not found in "
        "inventory/phase2/devices.yaml"
    )


device_credentials = credentials.get(
    DEVICE_NAME
)


if not device_credentials:
    raise RuntimeError(
        f"No credentials found for "
        f"{DEVICE_NAME} in "
        "inventory/phase2/credentials.yaml"
    )


HOST = r1["host"]

USERNAME = device_credentials[
    "username"
]

PASSWORD = device_credentials[
    "password"
]


# ---------------------------------------------------------------------
# RESTCONF endpoint
# ---------------------------------------------------------------------

BASE_URL = (
    f"https://{HOST}:{PORT}"
)

HOSTNAME_URL = (
    BASE_URL
    + "/restconf/data/"
    + "Cisco-IOS-XE-native:"
    + "native/hostname"
)


HEADERS = {
    "Accept": (
        "application/"
        "yang-data+json"
    )
}


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

def main() -> None:

    print("=" * 70)
    print("Phase 2 - RESTCONF R1 Test")
    print("=" * 70)

    print(
        f"Requesting:"
    )

    print(
        HOSTNAME_URL
    )

    print()

    response = requests.get(
        HOSTNAME_URL,

        auth=(
            USERNAME,
            PASSWORD,
        ),

        headers=HEADERS,

        verify=False,

        timeout=15,
    )

    print(
        f"HTTP status : "
        f"{response.status_code}"
    )

    print(
        f"Content-Type: "
        f"{response.headers.get('Content-Type')}"
    )

    # -------------------------------------------------------------
    # Validate HTTP response
    # -------------------------------------------------------------

    response.raise_for_status()

    # -------------------------------------------------------------
    # Parse JSON
    # -------------------------------------------------------------

    data = response.json()

    print()
    print("=" * 70)
    print("RESTCONF JSON response")
    print("=" * 70)

    print(
        data
    )

    # -------------------------------------------------------------
    # Extract hostname
    # -------------------------------------------------------------

    hostname_key = (
        "Cisco-IOS-XE-native:"
        "hostname"
    )

    hostname = data.get(
        hostname_key
    )

    if hostname is None:
        raise RuntimeError(
            "Hostname not found "
            "in RESTCONF response."
        )

    print()
    print("=" * 70)
    print("Parsed YANG data")
    print("=" * 70)

    print(
        f"Hostname: {hostname}"
    )

    if hostname != DEVICE_NAME:
        raise RuntimeError(
            f"Expected hostname "
            f"{DEVICE_NAME}, "
            f"received {hostname}"
        )

    print()
    print("=" * 70)
    print("RESTCONF R1 test PASSED")
    print("=" * 70)


if __name__ == "__main__":
    main()