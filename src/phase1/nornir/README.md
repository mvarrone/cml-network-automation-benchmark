# Phase 1 — Nornir + Netmiko

[← Phase 1 overview](../README.md) · [← Main README](../../../README.md)

| | |
|---|---|
| Library | Nornir 3.6.0 + nornir-netmiko 1.0.1 (Netmiko 4.8.0, Paramiko 4.0.0) |
| Concurrency | Nornir `threaded` runner (`num_workers`) |
| Transport | SSH (TCP/22) |
| Targets | 10 × IOSv (R1–R10) |
| Workers tested | 1, 2, 4, 5, 10 |
| Script | [`nornir_netmiko_benchmark.py`](nornir_netmiko_benchmark.py) |

Same Netmiko connections as the [threadpool](../threadpool/README.md) method, but orchestrated by Nornir: inventory, task execution and concurrency are handled by the framework.

---

## How It Works

### Inventory on the fly

Rather than maintaining a second permanent inventory, the script converts the project's `devices.yaml` + `credentials.yaml` into a temporary Nornir `SimpleInventory` (hosts / groups / defaults files):

```python
hosts[name] = {
    "hostname": device["host"],
    "username": ..., "password": ...,
    "platform": "ios",                     # cisco_ios → Nornir/NAPALM-style "ios"
    "connection_options": {"netmiko": {"extras": {"secret": ...}}},
}
```

### Runner and task

```python
nr = InitNornir(
    inventory={"plugin": "SimpleInventory", "options": {...}},
    runner={"plugin": "threaded", "options": {"num_workers": NUM_WORKERS}},
    logging={"enabled": False},
)

def backup_task(task):
    conn = task.host.get_connection("netmiko", task.nornir.config)
    conn.enable()
    config = conn.send_command("show running-config")

nr.run(task=backup_task)
```

---

## Running

```python
NUM_WORKERS = 10   # 1, 2, 4, 5, 10
```

```powershell
python .\src\phase1\nornir\nornir_netmiko_benchmark.py
```

---

## Results

| Workers | Avg | Median | Std. dev. | Min | Max | Self-speedup | Efficiency |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 10.750 s | 10.971 s | 0.516 s | 10.160 s | 11.119 s | 1.00× | 100% |
| 2 | 5.712 s | 5.731 s | 0.199 s | 5.504 s | 5.901 s | 1.88× | 94.1% |
| 4 | 3.638 s | 3.593 s | 0.093 s | 3.577 s | 3.745 s | 2.95× | 73.9% |
| 5 | 2.715 s | 2.643 s | 0.169 s | 2.593 s | 2.908 s | 3.96× | 79.2% |
| 10 | **1.578 s** | 1.605 s | 0.061 s | 1.508 s | 1.621 s | 6.81× | 68.1% |

Speedup vs sequential at 10 workers: **7.75×**. No failed backups.

### Compared with direct Netmiko `ThreadPoolExecutor`

| Workers | ThreadPool | Nornir | Difference |
|---:|---:|---:|---:|
| 1 | 11.868 s | 10.750 s | Nornir ~9.4% lower |
| 2 | 5.964 s | 5.712 s | Nornir ~4.2% lower |
| 4 | 3.883 s | 3.638 s | Nornir ~6.3% lower |
| 5 | 2.891 s | 2.715 s | Nornir ~6.1% lower |
| 10 | 1.766 s | 1.578 s | Nornir ~10.6% lower |

---

## Findings

- **No measurable orchestration penalty.** Nornir was slightly faster at every level, but runs were not interleaved, so this is not evidence that Nornir is intrinsically faster — only that its abstractions cost nothing visible here.
- You get inventory filtering, per-host results and a plugin ecosystem for free.
- Gotchas encountered:
  - The registered runner plugin name is `"threaded"`, not `"ThreadedRunner"`.
  - An early script name shadowed the installed `nornir_netmiko` package and broke imports — hence `nornir_netmiko_benchmark.py`.

---

## Output

```text
backups/phase1/nornir/<run_id>/R1.cfg … R10.cfg
results/phase1/nornir/<run_id>/results.csv
```

CSV columns: `run_id, method, workers, device, host, duration_s, success, bytes, lines, error`.
