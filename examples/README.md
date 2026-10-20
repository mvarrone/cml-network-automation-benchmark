# Example Outputs

[← Back to main README](../README.md)

The real `backups/` and `results/` folders are generated on every run and are git-ignored. This folder keeps **one representative run per method** so you can see exactly what each benchmark produces without running it.

Each example is a copy of a real, fully successful run at that method's highest concurrency level:

```text
examples/<phase>/<method>/
├── results.csv     ← per-device metrics (same file as results/<phase>/<method>/<run_id>/results.csv)
└── backups/        ← saved configurations (same files as backups/<phase>/<method>/<run_id>/)
```

## Phase 1 — 10 × IOSv

| Method | Run ID | Concurrency | Per-device duration | Backup format | Example |
|---|---|---:|---:|---|---|
| Netmiko sequential | `20261009_190532` | 1 (sequential) | 0.992–1.289 s | `.cfg` | [sequential/](phase1/sequential/) |
| Netmiko threading | `20261009_190605` | 10 threads | 1.454–1.637 s | `.cfg` | [threading/](phase1/threading/) |
| Netmiko ThreadPoolExecutor | `20261009_190611` | 10 workers | 1.439–1.698 s | `.cfg` | [threadpool/](phase1/threadpool/) |
| Scrapli + asyncio | `20261009_190517` | 10 concurrent | 0.865–1.126 s | `.cfg` | [asyncio/](phase1/asyncio/) |
| Nornir + Netmiko | `20261009_193130` | 10 workers | 1.414–1.598 s | `.cfg` | [nornir/](phase1/nornir/) |
| pyATS + Unicon | `20261009_203106` | 10 workers | 3.286–3.369 s | `.cfg` | [pyats/](phase1/pyats/) |
| Legacy NETCONF | `20261009_233949` | 10 workers | 1.484–1.608 s | `.cfg` (CLI text extracted from XML) | [netconf/](phase1/netconf/) |

## Phase 2 — 4 × CSR1000v

| Method | Run ID | Concurrency | Per-device duration | Backup format | Example |
|---|---|---:|---:|---|---|
| NETCONF/YANG | `20261010_155709_551000` | 4 workers (repetition 3) | 0.883–0.899 s | `.xml` (`<native>` subtree) | [netconf_yang/](phase2/netconf_yang/) |
| RESTCONF | `20261010_155911_932381` | 4 workers (repetition 3) | 0.477–0.488 s | `.json` (`Cisco-IOS-XE-native:native`) | [restconf/](phase2/restconf/) |

Comparing the same router across methods is a quick way to see the [output differences](../docs/methodology.md#output-differences-between-methods) between libraries and protocols — e.g. `phase2/netconf_yang/backups/R1.xml` vs `phase2/restconf/backups/R1.json` hold the same YANG data in XML and JSON.

## Notes

- The CSV columns differ per method — see the [`results.csv` schema](../docs/methodology.md#resultscsv-columns).
- Batch wall time is printed to the console and is not stored in the CSV; the averaged batch times are in each method's README.
- The saved configurations come from the isolated lab and contain only lab credentials (hashed `automation` / `cisco` secrets).
- Inventory templates live next to the real files: [`inventory/phase1/*.example.yaml`](../inventory/phase1/) and [`inventory/phase2/*.example.yaml`](../inventory/phase2/).
