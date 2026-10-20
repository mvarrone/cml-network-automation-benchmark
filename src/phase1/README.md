# Phase 1 — CLI and Legacy Automation

[← Back to main README](../../README.md)

Phase 1 compares seven ways of backing up the running configuration of **10 Cisco IOSv routers** (IOS 15.9(3)M12, R1–R10, `192.168.1.11–20`).

![Phase 1 CML topology](../../docs/images/phase1-topology.png)

Importable lab: [`cml/topologies/phase1-iosv-10-routers.yaml`](../../cml/topologies/phase1-iosv-10-routers.yaml)

```text
connect → authenticate → show running-config → disconnect → save R<n>.cfg
```

Six methods use SSH CLI scraping with different libraries and concurrency models. The seventh uses IOSv's **legacy** NETCONF implementation (`netconf ssh`, TCP/22), which returns CLI text inside XML rather than a YANG model.

---

## Methods

| Method | Library / transport | Concurrency | Runtime | README |
|---|---|---|---|---|
| Sequential | Netmiko + Paramiko | none | Windows | [sequential/](sequential/README.md) |
| Manual threads | Netmiko + Paramiko | `threading.Thread`, one per device | Windows | [threading/](threading/README.md) |
| Thread pool | Netmiko + Paramiko | `ThreadPoolExecutor` | Windows | [threadpool/](threadpool/README.md) |
| Async | Scrapli + AsyncSSH | `asyncio` + `Semaphore` | Windows | [asyncio/](asyncio/README.md) |
| Nornir | Nornir + nornir-netmiko | Nornir `threaded` runner | Windows | [nornir/](nornir/README.md) |
| pyATS | pyATS + Unicon + OpenSSH | `ThreadPoolExecutor` | WSL2 | [pyats/](pyats/README.md) |
| Legacy NETCONF | ncclient (SSH subsystem) | `ThreadPoolExecutor` | Windows | [netconf/](netconf/README.md) |

---

## Results — Average Batch Wall Time (10 devices)

| Workers | ThreadPool | Scrapli asyncio | Nornir | pyATS | Legacy NETCONF |
|---:|---:|---:|---:|---:|---:|
| 1 | 11.868 s | 7.831 s | 10.750 s | 20.027 s | 10.587 s |
| 2 | 5.964 s | 4.598 s | 5.712 s | 10.404 s | 5.617 s |
| 4 | 3.883 s | 2.847 s | 3.638 s | 6.584 s | 3.550 s |
| 5 | 2.891 s | 2.332 s | 2.715 s | 4.824 s | 2.753 s |
| 10 | 1.766 s | **1.456 s** | 1.578 s | 3.288 s | 1.745 s |

Fixed-concurrency methods: **sequential 12.226 s**, **manual threading (10 threads) 1.691 s**.

### Ranking at Maximum Concurrency

| Method | Avg wall time | Speedup vs sequential |
|---|---:|---:|
| Scrapli + AsyncSSH (asyncio) | **1.456 s** | 8.40× |
| Nornir + Netmiko | 1.578 s | 7.75× |
| Netmiko manual threading | 1.691 s | 7.23× |
| Legacy NETCONF + ncclient | 1.745 s | 7.01× |
| Netmiko ThreadPoolExecutor | 1.766 s | 6.92× |
| pyATS + Unicon | 3.288 s | 3.72× |
| Netmiko sequential | 12.226 s | 1.00× |

### Self-Scaling Efficiency at 10 Workers

| Method | Speedup (T1 / T10) | Efficiency |
|---|---:|---:|
| Netmiko ThreadPoolExecutor | 6.72× | 67.2% |
| Nornir + Netmiko | 6.81× | 68.1% |
| Legacy NETCONF | 6.07× | 60.7% |
| pyATS + Unicon | 6.09× | 60.9% |
| Scrapli asyncio | 5.38× | 53.8% |

Scrapli scales "worst" relative to itself only because its single-session cost is already much lower (~0.78 s/device vs ~1.1–1.2 s for Netmiko and ~2.0 s for pyATS).

---

## Takeaways

- The workload is strongly I/O-bound: every concurrent approach gives a 6–8× gain at 10 sessions.
- Differences between the threaded Netmiko variants, Nornir and legacy NETCONF are within a few percent — normal lab variation.
- Scrapli + AsyncSSH + asyncio was fastest, but the comparison changes the whole stack (library, SSH implementation and concurrency model), not just "threads vs asyncio".
- pyATS pays a higher per-session price for a far richer framework, and ran under WSL2.

Caveats and terminology: [docs/methodology.md](../../docs/methodology.md). Legacy SSH algorithm handling: [docs/setup.md](../../docs/setup.md#legacy-ssh-compatibility-iosv).
