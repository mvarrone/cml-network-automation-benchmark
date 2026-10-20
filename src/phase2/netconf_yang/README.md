# Phase 2 — NETCONF/YANG with ncclient

[← Phase 2 overview](../README.md) · [← Main README](../../../README.md)

| | |
|---|---|
| Library | ncclient 0.7.1 (`device_params={"name": "iosxe"}`) + lxml 6.1.3 |
| Concurrency | `ThreadPoolExecutor` |
| Transport | NETCONF over SSH, **TCP/830** |
| Encoding | XML |
| Data model | `Cisco-IOS-XE-native:native` |
| Device feature | `netconf-yang` |
| Targets | 4 × CSR1000v (R1–R4), IOS XE 17.03.08a |
| Workers tested | 1, 2, 4 × 3 runs each |
| Script | [`netconf_yang_benchmark.py`](netconf_yang_benchmark.py) |
| R1 smoke test | [`test_r1_netconf_yang.py`](test_r1_netconf_yang.py) |

Modern, model-driven NETCONF: the router returns its configuration as a structured YANG data tree, unlike the CLI-text-in-XML of [legacy NETCONF](../../phase1/netconf/README.md).

---

## How It Works

A subtree filter limits `<get-config>` to the IOS XE native model:

```python
NATIVE_FILTER = """
<native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
</native>
"""

with manager.connect(
    host=host, port=830,
    username=username, password=password,
    hostkey_verify=False, allow_agent=False, look_for_keys=False,
    device_params={"name": "iosxe"},
    timeout=30,
) as connection:
    response = connection.get_config(source="running", filter=("subtree", NATIVE_FILTER))
```

The `<native>` element is then located with XPath, pretty-printed with `lxml` and saved as `R<n>.xml`.

### Capabilities

CSR1000v advertises ~520 capabilities, including NETCONF base 1.1, `writable-running`, `validate`, `xpath` and the YANG Library. The R1 smoke test checks these explicitly and reads the hostname through a `<native><hostname/></native>` filter.

---

## Running

```powershell
# validate R1: session, key capabilities, hostname via YANG
python .\src\phase2\netconf_yang\test_r1_netconf_yang.py

# one worker level, one run
python .\src\phase2\netconf_yang\netconf_yang_benchmark.py --workers 4

# one worker level, three runs
python .\src\phase2\netconf_yang\netconf_yang_benchmark.py --workers 1 --runs 3

# full experiment: 1, 2, 4 workers × 3 runs, with aggregate summary
python .\src\phase2\netconf_yang\netconf_yang_benchmark.py --workers all --runs 3
```

| Argument | Values | Default |
|---|---|---|
| `--workers` | `1`, `2`, `4`, `all` | `all` |
| `--runs` | integer ≥ 1 | `1` |

Router side: `netconf-yang` (see [Phase 2 bootstrap configs](../../../cml/phase2-router_configs_R1-R4/)).

---

## Results

Valid runs: `20261010_155652_659549` → `20261010_155709_551000` (9 runs, 36 device backups, 100% success).

| Workers | Runs | Average | Median | Std. dev. | Min | Max |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 3 | **3.388 s** | 3.264 s | 0.247 s | 3.229 s | 3.672 s |
| 2 | 3 | **1.667 s** | 1.634 s | 0.074 s | 1.614 s | 1.752 s |
| 4 | 3 | **0.868 s** | 0.876 s | 0.038 s | 0.827 s | 0.902 s |

| Workers | Speedup | Efficiency | Per-device mean |
|---:|---:|---:|---:|
| 1 | 1.00× | 100.0% | 0.845 s |
| 2 | 2.03× | 101.6% | 0.823 s |
| 4 | 3.90× | 97.6% | 0.850 s |

The 101.6% efficiency at 2 workers is timing noise, not super-linear scaling.

### Payload (4 devices, identical in every run)

| Metric | Total |
|---|---:|
| `raw_xml_bytes` — original NETCONF RPC reply | 20,684 B |
| `native_xml_bytes` — re-serialized `<native>` backup | 27,257 B |
| Lines in saved backups | 1,103 |

`native_xml_bytes` is larger than the raw reply because `lxml` re-serialization adds inherited namespace declarations and pretty-printing; it is **not** the on-wire size.

---

## Findings

- **Near-linear scaling**, and per-device latency stays flat (~0.82–0.85 s) as concurrency rises — four routers with one session each are not contending. Contrast with Phase 1, where per-device time grew with concurrency.
- ~42% slower than [RESTCONF](../restconf/README.md) for the same data, despite a slightly smaller raw payload. Each request pays for SSH key exchange + authentication + NETCONF `<hello>` capability exchange (≈520 capabilities) before the RPC.
- Session reuse (one persistent NETCONF session per device) would separate setup cost from steady-state RPC cost — on the [roadmap](../../../docs/lessons-learned.md#roadmap).

---

## Output

```text
backups/phase2/netconf_yang/<run_id>/R1.xml … R4.xml
results/phase2/netconf_yang/<run_id>/results.csv      # run_id = YYYYMMDD_HHMMSS_ffffff
```

CSV columns: `run_id, method, workers, repetition, device, host, duration_s, success, native_xml_bytes, raw_xml_bytes, lines, error`.

> Earlier run folders without microseconds (`20261010_1549xx`, `20261010_1552xx`) are preliminary runs from before the `--runs` / microsecond run-ID changes and use an older CSV schema.
