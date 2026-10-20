# Benchmark Methodology

[← Back to main README](../README.md)

## Workload

Every method performs the same logical task per device:

```text
connect → authenticate → retrieve running configuration → disconnect → save backup
```

| Phase | What is retrieved |
|---|---|
| Phase 1 (CLI methods) | `show running-config` text |
| Phase 1 (legacy NETCONF) | `<get-config source=running>` → CLI text inside `<cli-config-data-block>` |
| Phase 2 | `Cisco-IOS-XE-native:native` YANG subtree (XML via NETCONF, JSON via RESTCONF) |

---

## Timing

- Timer: `time.perf_counter()` (monotonic, high-resolution).
- **Primary metric: total batch wall-clock time** — from submitting the first device to the last device finishing.
- **Per-device duration** — measured inside each worker around connect → retrieve → disconnect. It is recorded in `results.csv` but must not be confused with batch time; under heavy concurrency per-device latency can *rise* while batch time falls.
- Saving the backup file happens after the per-device timer stops.

## Concurrency Levels and Repetitions

| Phase | Levels | Repetitions |
|---|---|---|
| Phase 1 | 1, 2, 4, 5, 10 (where configurable) | ≥ 3 per level for threadpool, asyncio, nornir, pyats, netconf; 2–3 for sequential/threading |
| Phase 2 | 1, 2, 4 | exactly 3 per level, automated with `--runs 3` |

Phase 1 scripts set concurrency with a module constant (`MAX_WORKERS`, `NUM_WORKERS` or `MAX_CONCURRENT`); Phase 2 scripts take `--workers` / `--runs` arguments.

---

## Output Files

```text
backups/<phase>/<method>/<run_id>/<device>.{cfg|xml|json}
results/<phase>/<method>/<run_id>/results.csv
```

`run_id` is `YYYYMMDD_HHMMSS` in Phase 1 and `YYYYMMDD_HHMMSS_ffffff` (microseconds) in Phase 2, to avoid collisions between automated back-to-back repetitions.

### `results.csv` columns

| Column | Meaning | Present in |
|---|---|---|
| `run_id`, `method`, `device`, `host` | Identification | all |
| `workers` / `max_concurrent` | Concurrency level | all except sequential/threading |
| `repetition` | Repetition index within a `--runs` series | Phase 2 |
| `duration_s` | Per-device duration | all |
| `success` | `True` / `False` | all |
| `bytes`, `lines` | Size of saved CLI config | Phase 1 |
| `raw_xml_bytes` | Raw NETCONF RPC reply size | Phase 1 netconf, Phase 2 netconf_yang |
| `native_xml_bytes` | Re-serialized `<native>` subtree (not on-wire size) | Phase 2 netconf_yang |
| `native_json_bytes` | Pretty-printed JSON backup size | Phase 2 restconf |
| `raw_body_bytes`, `http_status` | Raw HTTP body size and status code | Phase 2 restconf |
| `error` | Exception text on failure | all |

Batch wall time is printed to the console at the end of each run (Phase 2 also prints an aggregate summary across runs).

---

## Terminology

| Term | Meaning here |
|---|---|
| **Sequential** | One device at a time: `T_total ≈ T1 + T2 + … + Tn` |
| **Concurrent** | I/O-bound tasks overlap in time (threads, thread pools, Nornir runner, asyncio). Does not imply multi-core execution. |
| **Parallel** | Truly simultaneous execution on multiple cores/processes (e.g. `multiprocessing`) — not used; the workload is I/O-bound. |
| **Asynchronous** | A single-thread event loop progresses many waiting network operations (Scrapli + AsyncSSH + asyncio). |
| **Speedup** | `S = T1 / Tp` |
| **Parallel efficiency** | `E = S / p`. Values slightly above 100% in small samples are timing noise, not super-linear scaling. |

---

## Output Differences Between Methods

Methods retrieving the same logical configuration do not produce byte-identical files. Causes include line endings, command-echo and prompt handling, whitespace normalization, XML namespace serialization, JSON pretty-printing, protocol wrappers, and different representations of the same modeled data (XML vs JSON in Phase 2).

The project distinguishes **logical configuration retrieval** from **byte-for-byte equivalence**. Compare backups semantically before claiming raw equivalence.

---

## Benchmark Fairness and Caveats

1. **Different stacks, not just different concurrency models.** Each result includes library overhead, transport, authentication/session setup, initialization behavior, protocol implementation and serialization:

   | Method | Stack |
   |---|---|
   | Netmiko | Netmiko + Paramiko |
   | Scrapli | Scrapli + AsyncSSH + asyncio |
   | pyATS | pyATS + Unicon + OpenSSH |
   | NETCONF/YANG | ncclient + SSH + XML |
   | RESTCONF | requests + HTTPS + JSON |

2. **Windows vs WSL2.** pyATS ran under WSL2; all other methods under native Windows Python.
3. **Phase 1 vs Phase 2.** Different platforms (IOSv vs CSR1000v), sizes (10 vs 4), protocols and resource footprints. Do not merge them into one ranking.
4. **Runs were not interleaved.** Methods were tested at different times; differences of a few percent should not be over-interpreted.
5. **Unequal Phase 1 repetition counts.** Phase 2 uses a consistent 3 runs per level.
6. **Small lab.** Behaviour at 50–1000 devices may be dominated by SSH connection limits, device control-plane load, CPU/memory, file descriptors, scheduler behaviour, API rate limits or AAA infrastructure.
