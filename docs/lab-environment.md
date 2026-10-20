# Lab Environment

[← Back to main README](../README.md)

## Cisco Modeling Labs Host

```text
Cisco CML 2.10.1 Personal Edition
Hypervisor:          Microsoft Hyper-V
Host OS:             Windows 11
Host RAM:            ~32 GB
CML VM RAM:          20 GB (raised for Phase 2)
Management network:  192.168.1.0/24
```

The project uses two separate topologies because the platforms have very different resource requirements.

---

## Phase 1 Topology — 10 × IOSv

![Phase 1 CML topology](images/phase1-topology.png)

CML lab file: [`cml/topologies/phase1-iosv-10-routers.yaml`](../cml/topologies/phase1-iosv-10-routers.yaml)

```text
Cisco IOSv — IOS 15.9(3)M12 — R1–R10

                 MGMT-EXT
                    |
                 MGMT-SW
          / / / / /   \ \ \ \ \
        R1 R2 R3 R4 R5 R6 R7 R8 R9 R10
```

| Device | Management IP | Device | Management IP |
|---|---|---|---|
| R1 | 192.168.1.11 | R6 | 192.168.1.16 |
| R2 | 192.168.1.12 | R7 | 192.168.1.17 |
| R3 | 192.168.1.13 | R8 | 192.168.1.18 |
| R4 | 192.168.1.14 | R9 | 192.168.1.19 |
| R5 | 192.168.1.15 | R10 | 192.168.1.20 |

Management interface: `GigabitEthernet0/0`.

| Capability | Supported |
|---|---|
| SSH (legacy SHA-1 algorithms) | Yes |
| Legacy NETCONF (`netconf ssh`, TCP/22) | Yes |
| NETCONF/YANG (TCP/830) | No |
| RESTCONF | No |

---

## Phase 2 Topology — 4 × CSR1000v

![Phase 2 CML topology](images/phase2-topology.png)

CML lab file: [`cml/topologies/phase2-csr1000v-4-routers.yaml`](../cml/topologies/phase2-csr1000v-4-routers.yaml)

```text
Cisco CSR1000v — IOS XE 17.03.08a — R1–R4
3 GB RAM + 1 vCPU per node

             MGMT-EXT
                |
             MGMT-SW
          /   /   \   \
        R1   R2   R3   R4
```

| Device | Management IP |
|---|---|
| R1 | 192.168.1.31 |
| R2 | 192.168.1.32 |
| R3 | 192.168.1.33 |
| R4 | 192.168.1.34 |

Management interface: `GigabitEthernet1`.

| Capability | Supported |
|---|---|
| NETCONF/YANG | Yes — TCP/830 (≈520 capabilities advertised, YANG Library present) |
| RESTCONF | Yes — HTTPS/443 |

### Host Resource Limit

With four CSR1000v nodes running, Windows host memory utilization was already ~98%. A fifth node was not attempted, so Phase 2 is intentionally limited to four routers. **Phase 1 and Phase 2 are not identical topology-size experiments.**

---

## Router Bootstrap Configurations

The [`cml/`](../cml/) folder contains the configuration pasted into each router plus the commands used to validate them manually.

| Path | Contents |
|---|---|
| [`cml/topologies/`](../cml/topologies/) | Importable CML lab files (`.yaml`) for both phases, with the bootstrap configs embedded |
| [`cml/phase1-router_configs_R1-R10/`](../cml/phase1-router_configs_R1-R10/) | IOSv bootstrap configs (local user, SSHv2, RSA keys, management IP, `netconf ssh`) |
| [`…/extra_validations/`](../cml/phase1-router_configs_R1-R10/extra_validations/) | PowerShell ping sweeps used to confirm reachability |
| [`cml/phase2-router_configs_R1-R4/`](../cml/phase2-router_configs_R1-R4/) | CSR1000v bootstrap configs (adds `ip http secure-server`, `netconf-yang`, `restconf`) |
| [`…/extra_validations/`](../cml/phase2-router_configs_R1-R4/extra_validations/) | Hostname / YANG capability checks, `curl` RESTCONF validation, IOS XE `show` commands |

Minimal Phase 2 model-driven configuration:

```text
ip http authentication local
ip http secure-server
netconf-yang
restconf
```

---

## Importing the Topologies into CML

1. In the CML **Dashboard**, click **Import**.
2. Select [`phase1-iosv-10-routers.yaml`](../cml/topologies/phase1-iosv-10-routers.yaml) or [`phase2-csr1000v-4-routers.yaml`](../cml/topologies/phase2-csr1000v-4-routers.yaml) and confirm.
3. Open the lab and adapt it to your environment **before starting it**:
   - **External connector** — point `MGMT-EXT` at the bridge that reaches your management network (e.g. *System Bridge*).
   - **Management IPs** — the configs use `192.168.1.11–20` (Phase 1) and `192.168.1.31–34` (Phase 2). Change them in each node's configuration if that range is in use on your LAN, and update `inventory/phaseN/devices.yaml` to match.
   - **Images** — the lab needs the `iosv` and `csr1000v` node definitions/images from the CML reference platform.
4. Start the lab. Routers boot with SSH, a local user and the required NETCONF/RESTCONF features already configured.
5. Run the `test_r1_*.py` scripts to validate reachability (see [docs/setup.md](setup.md#validation-scripts)).

Resource needs: Phase 1 is light (IOSv); Phase 2 needs ~3 GB RAM per CSR1000v — see [Host resource limit](#host-resource-limit).

> The embedded configs contain the lab-only credentials also found in the `cml/` text files. Change them if your CML is reachable from anything other than an isolated lab network.

---

## Hyper-V / CML Troubleshooting

### Nested virtualization

CML runs as a Hyper-V VM and needs nested virtualization plus MAC spoofing for the external management bridge:

```powershell
Set-VMProcessor -VMName CML_2.10 -ExposeVirtualizationExtensions $true

Get-VMNetworkAdapter -VMName CML_2.10 |
    Set-VMNetworkAdapter -MacAddressSpoofing On
```

### CML link "Running" toggle

An interface can be `no shutdown` in IOS and still be unusable if the CML link itself is not running.

```text
Open link → Link Statistics → enable "Running"
```

Check both ends of the link when connectivity is unexpectedly down.
