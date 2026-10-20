from pathlib import Path

import yaml
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


r1 = next(
    device
    for device in devices
    if device["name"] == "R1"
)


r1_credentials = credentials["R1"]


# ---------------------------------------------------------------------
# Connection information
# ---------------------------------------------------------------------

HOST = r1["host"]
PORT = 22

USERNAME = r1_credentials["username"]
PASSWORD = r1_credentials["password"]


# ---------------------------------------------------------------------
# Connect using NETCONF
# ---------------------------------------------------------------------

print("=" * 70)
print("Phase 1 - Legacy NETCONF R1 Test")
print("=" * 70)

print(
    f"Connecting to R1 ({HOST}:{PORT})..."
)


with manager.connect(
    host=HOST,
    port=PORT,

    username=USERNAME,
    password=PASSWORD,

    hostkey_verify=False,

    allow_agent=False,
    look_for_keys=False,

    timeout=15,
) as connection:

    print()
    print("NETCONF session established.")

    print(
        f"Session ID: "
        f"{connection.session_id}"
    )

    # -------------------------------------------------------------
    # Server capabilities
    # -------------------------------------------------------------

    print()
    print("=" * 70)
    print("Server capabilities")
    print("=" * 70)

    for capability in connection.server_capabilities:
        print(capability)

    # -------------------------------------------------------------
    # Retrieve running configuration
    # -------------------------------------------------------------

    print()
    print("=" * 70)
    print("get-config source=running")
    print("=" * 70)

    response = connection.get_config(
        source="running"
    )

    print(
        response.xml
    )


print()
print("=" * 70)
print("Legacy NETCONF R1 test completed")
print("=" * 70)