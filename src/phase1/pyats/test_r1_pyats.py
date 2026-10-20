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
        "No credentials found for R1"
    )


# ---------------------------------------------------------------------
# Build pyATS testbed dynamically
# ---------------------------------------------------------------------

testbed_data = {
    "testbed": {
        "name": "cml-benchmark",
    },

    "devices": {
        "R1": {
            "os": "ios",
            "platform": "iosv",
            "type": "router",

            "credentials": {
                "default": {
                    "username": (
                        r1_credentials[
                            "username"
                        ]
                    ),

                    "password": (
                        r1_credentials[
                            "password"
                        ]
                    ),
                },

                "enable": {
                    "password": (
                        r1_credentials.get(
                            "secret",
                            "",
                        )
                    ),
                },
            },

            "connections": {
                "cli": {
                    "protocol": "ssh",
                    "ip": r1["host"],

                    "ssh_options": (
                        "-o KexAlgorithms="
                        "+diffie-hellman-group14-sha1 "
                        "-o KexAlgorithms="
                        "+diffie-hellman-group-exchange-sha1 "
                        "-o HostKeyAlgorithms="
                        "+ssh-rsa"
                    ),

                    "settings": {
                        "GRACEFUL_DISCONNECT_WAIT_SEC": 0,
                        "POST_DISCONNECT_WAIT_SEC": 0,
                    },
                },
            },
        },
    },
}


# ---------------------------------------------------------------------
# Load testbed
# ---------------------------------------------------------------------

testbed = loader.load(
    testbed_data
)

device = testbed.devices[
    "R1"
]


# ---------------------------------------------------------------------
# Connect and test
# ---------------------------------------------------------------------

print("=" * 70)
print("Phase 1 - pyATS/Unicon R1 Test")
print("=" * 70)

print(
    f"Connecting to R1 "
    f"({r1['host']})..."
)


device.connect(
    via="cli",
    learn_hostname=False,
    log_stdout=True,

    init_exec_commands=[
        "term length 0",
        "term width 0",
    ],

    init_config_commands=[],
)


print()
print("=" * 70)
print("show ip interface brief")
print("=" * 70)


output = device.execute(
    "show ip interface brief"
)


print(
    output
)


device.disconnect()


print()
print("=" * 70)
print("pyATS/Unicon R1 test completed")
print("=" * 70)