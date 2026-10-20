# Phase 1 — Scrapli + AsyncSSH + asyncio

[← Phase 1 overview](../README.md) · [← Main README](../../../README.md)

| | |
|---|---|
| Library | Scrapli 2025.1.30 (`AsyncScrapli`) + AsyncSSH 2.24.1 |
| Concurrency | `asyncio` event loop, limited by `asyncio.Semaphore` |
| Transport | SSH (TCP/22) via AsyncSSH |
| Targets | 10 × IOSv (R1–R10) |
| Concurrency tested | 1, 2, 4, 5, 10 |
| Script | [`scrapli_async_benchmark.py`](scrapli_async_benchmark.py) |

The fastest Phase 1 method: a single-threaded event loop drives all SSH sessions, with a semaphore capping how many run at once.

---

## How It Works

```python
semaphore = asyncio.Semaphore(MAX_CONCURRENT)

async def backup_device(device):
    async with semaphore:
        async with AsyncScrapli(**connection_params) as conn:   # transport="asyncssh"
            response = await conn.send_command("show running-config")
            config = response.result

results = await asyncio.gather(*(backup_device(d) for d in devices))
```

### Legacy SSH options

IOSv only offers SHA-1-era algorithms, enabled explicitly through AsyncSSH transport options:

```python
"platform": "cisco_iosxe",
"transport": "asyncssh",
"auth_strict_key": False,
"transport_options": {
    "asyncssh": {
        "known_hosts": None,
        "client_keys": None,
        "kex_algs": ["diffie-hellman-group14-sha1", "diffie-hellman-group-exchange-sha1"],
        "server_host_key_algs": ["ssh-rsa"],
    }
},
```

Cryptography deprecation warnings about finite-field DH are expected. Lab-only — see [docs/setup.md](../../../docs/setup.md#legacy-ssh-compatibility-iosv).

---

## Running

```python
MAX_CONCURRENT = 10   # 1, 2, 4, 5, 10
```

```powershell
python .\src\phase1\asyncio\scrapli_async_benchmark.py
```

Pin `scrapli==2025.1.30` — a newer release required a build dependency that was unavailable for the tested Windows/Python version.

---

## Results

| Max concurrent | Avg | Median | Std. dev. | Min | Max |
|---:|---:|---:|---:|---:|---:|
| 1 | 7.831 s | 7.870 s | 0.241 s | 7.573 s | 8.050 s |
| 2 | 4.598 s | 4.438 s | 0.335 s | 4.372 s | 4.983 s |
| 4 | 2.847 s | 2.863 s | 0.147 s | 2.693 s | 2.986 s |
| 5 | 2.332 s | 2.336 s | 0.190 s | 2.140 s | 2.519 s |
| 10 | **1.456 s** | 1.440 s | 0.067 s | 1.398 s | 1.530 s |

| Concurrency | Self-speedup | Efficiency | Speedup vs Netmiko sequential |
|---:|---:|---:|---:|
| 1 | 1.00× | 100% | 1.56× |
| 2 | 1.70× | 85.1% | 2.66× |
| 4 | 2.75× | 68.8% | 4.29× |
| 5 | 3.36× | 67.2% | 5.24× |
| 10 | 5.38× | 53.8% | **8.40×** |

Per-device time (all recorded runs): 0.781 s mean at concurrency 1 → 1.125 s at concurrency 10. No failures.

---

## Findings

- **Fastest even without concurrency.** At concurrency 1 Scrapli takes 7.8 s vs 11.9–12.2 s for Netmiko — ~0.78 s per device vs ~1.15–1.19 s. Much of the final advantage comes from lower per-session cost, not from asyncio itself.
- Lower self-efficiency than the threaded methods is a consequence of that low baseline: there is less waiting to overlap.
- **Do not read this as "asyncio is faster than threads".** The comparison changes the whole stack:

  ```text
  Netmiko : Netmiko + Paramiko + threads
  Scrapli : Scrapli + AsyncSSH + asyncio
  ```

  The correct conclusion is that this particular stack produced the lowest wall time on this IOSv workload.
- The semaphore gives the same bounded-concurrency control as `ThreadPoolExecutor(max_workers=…)`.

---

## Output

```text
backups/phase1/asyncio/<run_id>/R1.cfg … R10.cfg
results/phase1/asyncio/<run_id>/results.csv
```

CSV columns: `run_id, method, max_concurrent, device, host, duration_s, success, bytes, lines, error`.
