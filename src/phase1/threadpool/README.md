# Phase 1 — Netmiko ThreadPoolExecutor

[← Phase 1 overview](../README.md) · [← Main README](../../../README.md)

| | |
|---|---|
| Library | Netmiko 4.8.0 + Paramiko 4.0.0 |
| Concurrency | `concurrent.futures.ThreadPoolExecutor` (bounded) |
| Transport | SSH (TCP/22) |
| Targets | 10 × IOSv (R1–R10) |
| Workers tested | 1, 2, 4, 5, 10 |
| Script | [`netmiko_threadpool_benchmark.py`](netmiko_threadpool_benchmark.py) |

The standard-library way to run the Netmiko backup concurrently with a configurable cap on simultaneous SSH sessions.

---

## How It Works

```python
with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    future_to_device = {executor.submit(backup_device, d): d for d in devices}
    for future in as_completed(future_to_device):
        results.append(future.result())
```

The pool handles thread lifecycle, queuing and result collection — no manual `Lock` or `join()`.

---

## Running

Set the worker count at the top of the script, then run it:

```python
MAX_WORKERS = 10   # 1, 2, 4, 5, 10
```

```powershell
python .\src\phase1\threadpool\netmiko_threadpool_benchmark.py
```

---

## Results

Three valid runs per worker level; all 10 routers backed up successfully in every run.

| Workers | Avg wall time | Std. dev. | Speedup vs sequential | Self-speedup | Efficiency |
|---:|---:|---:|---:|---:|---:|
| 1 | 11.868 s | 0.105 s | 1.03× | 1.00× | 100% |
| 2 | 5.964 s | 0.231 s | 2.05× | 1.99× | 99.5% |
| 4 | 3.883 s | 0.094 s | 3.15× | 3.06× | 76.4% |
| 5 | 2.891 s | 0.032 s | 4.23× | 4.11× | 82.1% |
| 10 | **1.766 s** | 0.082 s | **6.92×** | 6.72× | 67.2% |

Per-device time (all recorded runs):

| Workers | Mean | Min | Max |
|---:|---:|---:|---:|
| 1 | 1.185 s | 1.072 s | 1.367 s |
| 2 | 1.173 s | 1.066 s | 1.348 s |
| 4 | 1.342 s | 1.109 s | 1.545 s |
| 5 | 1.386 s | 1.214 s | 1.546 s |
| 10 | 1.619 s | 1.439 s | 1.850 s |

---

## Findings

- Near-perfect scaling up to 2 workers; efficiency then drops as per-device latency climbs ~37% from 1 to 10 workers.
- At 10 workers it lands within noise of [manual threading](../threading/README.md) (1.691 s) — the pool adds no meaningful overhead.
- Worker counts that don't divide 10 evenly (4) show lower efficiency: 3 "waves" are needed instead of 2.5.
- Recommended default pattern for simple concurrent scripts: explicit, bounded, standard library only.

---

## Output

```text
backups/phase1/threadpool/<run_id>/R1.cfg … R10.cfg
results/phase1/threadpool/<run_id>/results.csv
```

CSV columns: `run_id, method, workers, device, host, duration_s, success, bytes, lines, error`.
