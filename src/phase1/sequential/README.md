# Phase 1 — Netmiko Sequential

[← Phase 1 overview](../README.md) · [← Main README](../../../README.md)

| | |
|---|---|
| Library | Netmiko 4.8.0 + Paramiko 4.0.0 |
| Concurrency | None — one device at a time |
| Transport | SSH (TCP/22) |
| Targets | 10 × IOSv (R1–R10) |
| Script | [`netmiko_sequential_benchmark.py`](netmiko_sequential_benchmark.py) |
| R1 smoke test | [`test_r1_netmiko_seq.py`](test_r1_netmiko_seq.py) |

The **baseline** for every other Phase 1 method: a plain `for` loop that connects to each router, runs `show running-config` and saves the output.

---

## How It Works

```python
for device in devices:
    with ConnectHandler(**connection_params) as connection:   # SSH connect + auth
        if secret:
            connection.enable()
        config = connection.send_command("show running-config")
    # per-device timer stops here, then the backup is written
```

Total time is the sum of every device's time:

```text
R1 → R2 → R3 → … → R10        T_total ≈ T1 + T2 + … + T10
```

---

## Running

```powershell
# optional: validate connectivity to R1 first
python .\src\phase1\sequential\test_r1_netmiko_seq.py

python .\src\phase1\sequential\netmiko_sequential_benchmark.py
```

No concurrency setting — the script always processes the full inventory serially.

---

## Results

| Metric | Value |
|---|---:|
| Batch wall time (10 devices) | **12.226 s** |
| Per-device time (all recorded runs) | mean 1.149 s · min 0.992 s · max 1.327 s |
| Success rate | 30 / 30 device backups |

This 12.226 s figure is the reference used for "speedup vs sequential" across Phase 1.

---

## Findings

**Pros**
- Simplest possible implementation; deterministic ordering.
- Easy to debug — logs and errors appear in device order.

**Cons**
- Does not scale: SSH handshake, authentication and command wait time accumulate linearly.
- At ~1.15 s per device, 1,000 devices would take ~19 minutes.

---

## Output

```text
backups/phase1/sequential/<run_id>/R1.cfg … R10.cfg
results/phase1/sequential/<run_id>/results.csv
```

CSV columns: `run_id, method, device, host, duration_s, success, bytes, lines, error`.
