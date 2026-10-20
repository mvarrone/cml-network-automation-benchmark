# Phase 1 — Netmiko Manual Threading

[← Phase 1 overview](../README.md) · [← Main README](../../../README.md)

| | |
|---|---|
| Library | Netmiko 4.8.0 + Paramiko 4.0.0 |
| Concurrency | `threading.Thread` — **one thread per device** (10) |
| Transport | SSH (TCP/22) |
| Targets | 10 × IOSv (R1–R10) |
| Script | [`netmiko_threading_benchmark.py`](netmiko_threading_benchmark.py) |

The first concurrent version: same Netmiko backup function as the [sequential baseline](../sequential/README.md), but every router gets its own thread.

---

## How It Works

```python
def worker(device):
    result = backup_device(device)
    with results_lock:            # shared list protected by a Lock
        results.append(result)

threads = [threading.Thread(target=worker, args=(d,), name=f"thread-{d['name']}")
           for d in devices]

for t in threads: t.start()
for t in threads: t.join()
```

Results are re-sorted into inventory order before being written to CSV, since threads finish in arbitrary order.

---

## Running

```powershell
python .\src\phase1\threading\netmiko_threading_benchmark.py
```

The thread count always equals the number of devices in `inventory/phase1/devices.yaml`; there is no worker limit to tune. For bounded concurrency see [threadpool](../threadpool/README.md).

---

## Results

| Run | Batch wall time |
|---|---:|
| Valid run 1 | 1.757 s |
| Valid run 2 | 1.625 s |
| **Average** | **1.691 s** |

| Metric | Value |
|---|---:|
| Speedup vs sequential (12.226 s) | **~7.23×** |
| Per-device time (all recorded runs) | mean 1.566 s · min 1.435 s · max 1.754 s |
| Success rate | 30 / 30 device backups |

---

## Findings

- The backup workload is strongly **I/O-bound**: threads spend nearly all their time waiting on the network, so the GIL is not a bottleneck.
- **Per-device latency rose** from ~1.15 s (sequential) to ~1.57 s while **batch time fell** ~7×. The two metrics must be reported separately.
- Unbounded "one thread per device" is fine for 10 routers but does not protect devices, the host or AAA servers at larger scale — a pool with a cap is the safer pattern.
- Requires manual handling of shared state (`Lock`) and ordering.

---

## Output

```text
backups/phase1/threading/<run_id>/R1.cfg … R10.cfg
results/phase1/threading/<run_id>/results.csv
```

CSV columns: `run_id, method, device, host, duration_s, success, bytes, lines, error`.
