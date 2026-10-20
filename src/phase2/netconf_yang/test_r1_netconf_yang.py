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
PORT = 830


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
# Cisco IOS XE native YANG namespace
# ---------------------------------------------------------------------

CISCO_NATIVE_NS = (
    "http://cisco.com/ns/yang/"
    "Cisco-IOS-XE-native"
)


# ---------------------------------------------------------------------
# NETCONF subtree filter
# ---------------------------------------------------------------------

HOSTNAME_FILTER = f"""
<native xmlns="{CISCO_NATIVE_NS}">
    <hostname/>
</native>
"""


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

def main() -> None:

    print("=" * 70)
    print("Phase 2 - NETCONF/YANG R1 Test")
    print("=" * 70)

    print(
        f"Connecting to {DEVICE_NAME} "
        f"({HOST}:{PORT})..."
    )

    with manager.connect(
        host=HOST,
        port=PORT,

        username=USERNAME,
        password=PASSWORD,

        hostkey_verify=False,

        allow_agent=False,
        look_for_keys=False,

        device_params={
            "name": "iosxe"
        },

        timeout=15,
    ) as connection:

        print()
        print(
            "NETCONF/YANG session established."
        )

        print(
            f"Session ID   : "
            f"{connection.session_id}"
        )

        capabilities = list(
            connection.server_capabilities
        )

        print(
            f"Capabilities : "
            f"{len(capabilities)}"
        )

        # -------------------------------------------------------------
        # Verify important capabilities
        # -------------------------------------------------------------

        print()
        print("=" * 70)
        print(
            "Selected NETCONF capabilities"
        )
        print("=" * 70)

        capability_checks = [
            "netconf:base:1.1",
            "writable-running",
            "validate",
            "xpath",
            "yang-library",
        ]

        capability_text = "\n".join(
            str(capability)
            for capability in capabilities
        )

        for capability in capability_checks:

            supported = (
                capability
                in capability_text
            )

            print(
                f"{capability:<25} "
                f"{'SUPPORTED' if supported else 'NOT FOUND'}"
            )

        # -------------------------------------------------------------
        # Retrieve hostname through YANG
        # -------------------------------------------------------------

        print()
        print("=" * 70)

        print(
            "GET-CONFIG using "
            "Cisco-IOS-XE-native YANG model"
        )

        print("=" * 70)

        response = connection.get_config(
            source="running",
            filter=(
                "subtree",
                HOSTNAME_FILTER,
            ),
        )

        print()
        print("Raw NETCONF XML:")

        print(
            response.xml
        )

        # -------------------------------------------------------------
        # Parse hostname
        # -------------------------------------------------------------

        root = etree.fromstring(
            response.xml.encode(
                "utf-8"
            )
        )

        hostname_nodes = root.xpath(
            "//*[local-name()='hostname']"
        )

        if not hostname_nodes:
            raise RuntimeError(
                "Hostname not found "
                "in NETCONF response."
            )

        hostname = (
            hostname_nodes[0].text
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

    print(
        "NETCONF/YANG R1 test PASSED"
    )

    print("=" * 70)


if __name__ == "__main__":
    main()