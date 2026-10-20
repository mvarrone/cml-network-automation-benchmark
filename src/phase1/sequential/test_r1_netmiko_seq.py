from pathlib import Path

import yaml
from netmiko import ConnectHandler

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


r1 = next(
    (
        device
        for device in devices
        if device.get("name") == "R1"
    ),
    None,
)


if r1 is None:
    raise RuntimeError(
        "R1 was not found in "
        "inventory/phase1/devices.yaml"
    )


r1_credentials = credentials.get(
    "R1"
)


if not r1_credentials:
    raise RuntimeError(
        "No credentials found for R1 in "
        "inventory/phase1/credentials.yaml"
    )


# ---------------------------------------------------------------------
# Connection parameters
# ---------------------------------------------------------------------

device = {
    "device_type": r1["device_type"],
    "host": r1["host"],
    "username": r1_credentials["username"],
    "password": r1_credentials["password"],
    "secret": r1_credentials.get(
        "secret",
        "",
    ),
}


# ---------------------------------------------------------------------
# Test connection
# ---------------------------------------------------------------------

print("=" * 70)
print("Phase 1 - Netmiko Sequential R1 Test")
print("=" * 70)

print(
    f"Connecting to R1 "
    f"({device['host']})..."
)

print()


with ConnectHandler(
    **device
) as connection:

    if device["secret"]:
        connection.enable()

    output = connection.send_command(
        "show ip interface brief"
    )


print(
    output
)


print()
print("=" * 70)
print("Netmiko R1 test completed")
print("=" * 70)