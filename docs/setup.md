# Setup and Reproducibility

[← Back to main README](../README.md)

## Python Environments

Two environments are used: native Windows for almost everything, and WSL2 for pyATS.

### Native Windows — `requirements.txt`

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Core tested versions:

| Package | Version | Used by |
|---|---|---|
| Python | 3.14.8 | all Windows benchmarks |
| Netmiko | 4.8.0 | sequential, threading, threadpool, nornir |
| Paramiko | **4.0.0** (pinned) | Netmiko transport |
| Scrapli | **2025.1.30** (pinned) | asyncio |
| AsyncSSH | 2.24.1 | asyncio |
| Nornir / nornir-netmiko | 3.6.0 / 1.0.1 | nornir |
| ncclient | 0.7.1 | Phase 1 netconf, Phase 2 netconf_yang |
| lxml | 6.1.3 | XML parsing |
| requests | 2.34.2 | Phase 2 restconf |

### WSL2 — `requirements-wsl.txt`

pyATS has no native Windows distribution for the tested release, so it runs in WSL2:

```text
Ubuntu 26.04.1 LTS · Python 3.13.16 · pyATS 26.9 · Unicon 26.9 · Genie 26.9
```

```bash
# keep the venv on the Linux filesystem (see note below)
uv venv ~/.venvs/cml-benchmark
source ~/.venvs/cml-benchmark/bin/activate
uv pip install -r requirements-wsl.txt

# export after changes
uv pip freeze --python ~/.venvs/cml-benchmark/bin/python > requirements-wsl.txt
```

> **Do not put the WSL virtual environment under `/mnt/c/...`.** Imports of `pyats.topology` and `unicon` took ~16 s each from the Windows filesystem and well under 1 s from `/home/...`. The repository itself can stay on `/mnt/c`. Details in [pyATS README](../src/phase1/pyats/README.md#wsl-filesystem-performance).

---

## Inventory and Credentials

Each phase has its own inventory in `inventory/phaseN/`. Only the `.example.yaml` files are committed — copy them to `devices.yaml` / `credentials.yaml` and fill in your values.

`devices.yaml`:

```yaml
devices:
  - name: R1
    host: 192.168.1.31
    device_type: cisco_iosxe   # cisco_ios for Phase 1
```

`credentials.yaml` (keyed by device name):

```yaml
R1:
  username: YOUR_USERNAME
  password: YOUR_PASSWORD
  secret: YOUR_ENABLE_SECRET   # Phase 1 only
```

`.gitignore` excludes the real credential files, virtual environments and the generated `backups/` and `results/` folders. A representative sample of the outputs is committed under [`examples/`](../examples/README.md).

Plaintext YAML credentials are acceptable only because this is an isolated lab. Production setups should use TACACS+/RADIUS, HashiCorp Vault, cloud secret managers, CI/CD secret stores or runtime injection.

---

## Validation Scripts

Several method folders include a `test_r1_*.py` script that connects only to R1. Run these first to confirm reachability, credentials and protocol support before a full benchmark.

| Script | Checks |
|---|---|
| [`src/phase1/sequential/test_r1_netmiko_seq.py`](../src/phase1/sequential/test_r1_netmiko_seq.py) | Netmiko SSH login + enable + `show ip interface brief` |
| [`src/phase1/pyats/test_r1_pyats.py`](../src/phase1/pyats/test_r1_pyats.py) | In-memory pyATS testbed + Unicon connection + `show ip interface brief` |
| [`src/phase1/netconf/test_r1_netconf.py`](../src/phase1/netconf/test_r1_netconf.py) | Legacy NETCONF session, capability list, `get-config` running |
| [`src/phase2/netconf_yang/test_r1_netconf_yang.py`](../src/phase2/netconf_yang/test_r1_netconf_yang.py) | NETCONF on TCP/830, key capabilities (base 1.1, writable-running, validate, xpath, yang-library), hostname via YANG subtree filter |
| [`src/phase2/restconf/test_r1_restconf.py`](../src/phase2/restconf/test_r1_restconf.py) | RESTCONF GET of `Cisco-IOS-XE-native:native/hostname` as YANG JSON |

---

## Legacy SSH Compatibility (IOSv)

IOSv 15.9(3)M12 only offers SHA-1-era SSH algorithms:

```text
KEX:       diffie-hellman-group-exchange-sha1, diffie-hellman-group14-sha1
Host key:  ssh-rsa
```

Modern clients reject these by default. How each stack was made to work:

| Stack | Fix |
|---|---|
| Netmiko / Paramiko | Pin **Paramiko 4.0.0** — 5.0.0 failed against IOSv |
| Scrapli / AsyncSSH | `transport_options.asyncssh.kex_algs` / `server_host_key_algs` |
| pyATS / Unicon (OpenSSH) | `ssh_options` with `-o KexAlgorithms=+… -o HostKeyAlgorithms=+ssh-rsa` |
| ncclient (legacy NETCONF) | Works with the pinned Paramiko |

Manual OpenSSH equivalent:

```bash
ssh -oKexAlgorithms=+diffie-hellman-group14-sha1 -oHostKeyAlgorithms=+ssh-rsa automation@192.168.1.11
```

Cryptography deprecation warnings about finite-field DH are expected. **This is a lab-only compatibility constraint, not a recommendation to enable SHA-1 algorithms in production.**

---

## Other Compatibility Notes

- **Scrapli version** — a newer release pulled a build dependency unavailable for the tested Windows/Python combination; `2025.1.30` works.
- **Module shadowing** — an early script name collided with the installed `nornir_netmiko` package. Never name local modules after packages you import.
- **Nornir runner name** — the registered plugin is `"threaded"`, not `"ThreadedRunner"`.
- **pyATS needs Genie** — installing only pyATS + Unicon fails during plugin discovery.
