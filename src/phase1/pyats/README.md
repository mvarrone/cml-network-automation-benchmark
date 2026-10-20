# Phase 1 — pyATS + Unicon

[← Phase 1 overview](../README.md) · [← Main README](../../../README.md)

| | |
|---|---|
| Library | pyATS 26.9 + Unicon 26.9 + Genie 26.9 |
| Concurrency | `ThreadPoolExecutor` |
| Transport | SSH via system OpenSSH (spawned by Unicon) |
| Runtime | **WSL2** — Ubuntu 26.04.1 LTS, Python 3.13.16 |
| Targets | 10 × IOSv (R1–R10) |
| Workers tested | 1, 2, 4, 5, 10 |
| Script | [`pyats_unicon_benchmark.py`](pyats_unicon_benchmark.py) |
| R1 smoke test | [`test_r1_pyats.py`](test_r1_pyats.py) |

Cisco's test/automation framework, used here purely as a connection and command-execution layer. It required the most tuning to produce a fair, read-only benchmark.

---

## How It Works

An in-memory pyATS testbed is built from `devices.yaml` + `credentials.yaml` and loaded with `pyats.topology.loader`:

```python
"connections": {
    "cli": {
        "protocol": "ssh",
        "ip": host,
        "ssh_options": "-o KexAlgorithms=+diffie-hellman-group14-sha1 "
                       "-o KexAlgorithms=+diffie-hellman-group-exchange-sha1 "
                       "-o HostKeyAlgorithms=+ssh-rsa",
        "settings": {
            "GRACEFUL_DISCONNECT_WAIT_SEC": 0,
            "POST_DISCONNECT_WAIT_SEC": 0,
        },
    },
},
```

Each worker connects, executes and disconnects:

```python
device.connect(
    via="cli",
    learn_hostname=False,
    log_stdout=False,
    init_exec_commands=["term length 0", "term width 0"],
    init_config_commands=[],
)
config = device.execute("show running-config")
device.disconnect()
```

---

## Running (WSL2)

```bash
source ~/.venvs/cml-benchmark/bin/activate

# optional: validate R1
python /mnt/c/Users/<user>/Documents/cml-network-automation-benchmark/src/phase1/pyats/test_r1_pyats.py

python /mnt/c/Users/<user>/Documents/cml-network-automation-benchmark/src/phase1/pyats/pyats_unicon_benchmark.py
```

Set concurrency in the script:

```python
MAX_WORKERS = 10   # 1, 2, 4, 5, 10
```

Environment setup: [docs/setup.md](../../../docs/setup.md#wsl2--requirements-wsltxt).

---

## Results

| Workers | Run 1 | Run 2 | Run 3 | Avg | Median | Std. dev. |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 19.990 s | 19.973 s | 20.118 s | **20.027 s** | 19.990 s | 0.065 s |
| 2 | 10.259 s | 10.525 s | 10.429 s | **10.404 s** | 10.429 s | 0.110 s |
| 4 | 6.449 s | 6.686 s | 6.616 s | **6.584 s** | 6.616 s | 0.099 s |
| 5 | 4.822 s | 4.837 s | 4.813 s | **4.824 s** | 4.822 s | 0.010 s |
| 10 | 3.112 s | 3.374 s | 3.379 s | **3.288 s** | 3.374 s | 0.125 s |

| Workers | Speedup | Efficiency |
|---:|---:|---:|
| 1 | 1.00× | 100% |
| 2 | 1.92× | 96.2% |
| 4 | 3.04× | 76.0% |
| 5 | 4.15× | 83.0% |
| 10 | 6.09× | 60.9% |

Per-device time: ~1.99 s mean at 1 worker → ~3.23 s at 10 workers. No failed backups. Speedup vs Netmiko sequential at 10 workers: 3.72×.

---

## Findings

### Higher per-session cost
At ~2 s per device, pyATS + Unicon costs roughly twice as much per session as Netmiko (spawning OpenSSH, Unicon state machine, prompt detection). In return it offers a much richer framework (Genie parsers, testbeds, test harness).

### Windows installation
```text
ERROR: Could not find a version that satisfies the requirement pyats
ERROR: No matching distribution found for pyats
```
No native Windows build was available, so the benchmark runs in WSL2 — an OS/runtime caveat when comparing against the Windows methods.

### Genie dependency
Installing only pyATS + Unicon + PyYAML failed during plugin discovery; Genie is required.

### Unicon modifies the config by default
Default initialization runs configuration commands (e.g. `no logging console`, `exec-timeout 0`). For a **read-only** backup benchmark this is unacceptable, so `init_config_commands=[]` and only terminal length/width exec commands are kept.

### Disconnect waits dominated timing
Early concurrent runs were dominated by Unicon's graceful/post-disconnect waits. Setting both to `0` was essential — a clear example of framework defaults distorting a benchmark.

### WSL filesystem performance
With the venv under `/mnt/c/Users/.../.venv-wsl`:

```text
from pyats.topology import loader   ~15.7 s
import unicon                       ~16.3 s
```

Moving it to `/home/user01/.venvs/cml-benchmark` reduced imports to well under 1 s. The repository can stay on `/mnt/c`; only the large Python environment needs to live on the Linux filesystem.

---

## Output

```text
backups/phase1/pyats/<run_id>/R1.cfg … R10.cfg
results/phase1/pyats/<run_id>/results.csv
```

CSV columns: `run_id, method, workers, device, host, duration_s, success, bytes, lines, error`.
