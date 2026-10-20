# Phase 2 — Model-Driven Automation

[← Back to main README](../../README.md)

Phase 2 retrieves the **same YANG configuration model** — `Cisco-IOS-XE-native:native` — from **4 Cisco CSR1000v routers** (IOS XE 17.03.08a, 3 GB RAM / 1 vCPU each, `192.168.1.31–34`) using two model-driven protocols.

![Phase 2 CML topology](../../docs/images/phase2-topology.png)

Importable lab: [`cml/topologies/phase2-csr1000v-4-routers.yaml`](../../cml/topologies/phase2-csr1000v-4-routers.yaml)

This is the cleanest protocol comparison in the project: same routers, same data model, same Python concurrency model (`ThreadPoolExecutor`), same run design (workers 1, 2, 4 × 3 runs each).

---

## Methods

| Method | Library | Transport | Encoding | Backup file | README |
|---|---|---|---|---|---|
| NETCONF/YANG | ncclient | SSH, TCP/830 | XML | `R<n>.xml` | [netconf_yang/](netconf_yang/README.md) |
| RESTCONF | requests | HTTPS, TCP/443 | `application/yang-data+json` | `R<n>.json` | [restconf/](restconf/README.md) |

Both scripts share the same CLI:

```powershell
python .\src\phase2\<method>\<method>_benchmark.py --workers {1|2|4|all} --runs N
```

---

## NETCONF/YANG vs RESTCONF

| Workers | NETCONF/YANG | RESTCONF | RESTCONF reduction |
|---:|---:|---:|---:|
| 1 | 3.388 s | **1.959 s** | ~42.2% |
| 2 | 1.667 s | **0.978 s** | ~41.3% |
| 4 | 0.868 s | **0.497 s** | ~42.7% |

| At 4 workers | NETCONF/YANG | RESTCONF |
|---|---:|---:|
| Speedup | 3.90× | 3.94× |
| Efficiency | 97.6% | 98.6% |
| Raw payload (4 devices) | 20,684 B XML | 21,165 B JSON |
| Saved backup (4 devices) | 27,257 B / 1,103 lines | 22,673 B / 1,115 lines |

All 36 device-retrievals per protocol (3 levels × 3 runs × 4 routers) succeeded.

---

## Interpretation

- **Both protocols scale almost linearly** across the four-router topology.
- **RESTCONF was consistently ~41–43% faster** — and not because of a smaller payload (its raw body was slightly *larger*).
- The gap reflects the full stacks being measured:

  ```text
  NETCONF  = SSH + NETCONF session/hello + ncclient + XML RPC + IOS XE NETCONF subsystem
  RESTCONF = TLS + HTTP + requests + JSON decoding + IOS XE RESTCONF subsystem
  ```

- This is an observed property of this CSR1000v / CML / Python environment, **not** a universal "RESTCONF is faster than NETCONF" rule. Session reuse (persistent NETCONF sessions, `requests.Session()`) is the obvious next experiment — see the [roadmap](../../docs/lessons-learned.md#roadmap).

Phase 2 was limited to four nodes by host RAM (~98% used) — see [docs/lab-environment.md](../../docs/lab-environment.md#host-resource-limit).
