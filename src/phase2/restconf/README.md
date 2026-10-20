# Phase 2 — RESTCONF with requests

[← Phase 2 overview](../README.md) · [← Main README](../../../README.md)

| | |
|---|---|
| Library | requests 2.34.2 |
| Concurrency | `ThreadPoolExecutor` |
| Transport | HTTPS, **TCP/443** (self-signed cert, verification disabled) |
| Encoding | `application/yang-data+json` |
| Data model | `Cisco-IOS-XE-native:native` |
| Device features | `ip http secure-server`, `ip http authentication local`, `restconf` |
| Targets | 4 × CSR1000v (R1–R4), IOS XE 17.03.08a |
| Workers tested | 1, 2, 4 × 3 runs each |
| Script | [`restconf_benchmark.py`](restconf_benchmark.py) |
| R1 smoke test | [`test_r1_restconf.py`](test_r1_restconf.py) |

Retrieves exactly the same YANG model as [NETCONF/YANG](../netconf_yang/README.md), but as JSON over a single HTTPS GET.

---

## How It Works

```python
RESTCONF_PATH = "/restconf/data/Cisco-IOS-XE-native:native"
HEADERS = {"Accept": "application/yang-data+json"}

response = requests.get(
    f"https://{host}:443{RESTCONF_PATH}",
    auth=(username, password),       # HTTP Basic, local AAA
    headers=HEADERS,
    verify=False,                    # lab-only: self-signed certificate
    timeout=30,
)
response.raise_for_status()
data = response.json()
native = data["Cisco-IOS-XE-native:native"]
```

The native subtree is re-serialized with `json.dumps(indent=2)` and saved as `R<n>.json`. `urllib3`'s `InsecureRequestWarning` is suppressed because certificate verification is intentionally off in this isolated lab.

Each request uses a fresh connection (`requests.get`, no `Session`), so the timing includes TCP + TLS setup for every device.

---

## Running

```powershell
# validate R1: GET Cisco-IOS-XE-native:native/hostname
python .\src\phase2\restconf\test_r1_restconf.py

# one worker level
python .\src\phase2\restconf\restconf_benchmark.py --workers 4

# full experiment: 1, 2, 4 workers × 3 runs, with aggregate summary
python .\src\phase2\restconf\restconf_benchmark.py --workers all --runs 3
```

| Argument | Values | Default |
|---|---|---|
| `--workers` | `1`, `2`, `4`, `all` | `all` |
| `--runs` | integer ≥ 1 | `1` |

Manual check with curl:

```bash
curl -k -u <user>:<pass> -H "Accept: application/yang-data+json" \
  https://192.168.1.31/restconf/data/Cisco-IOS-XE-native:native/hostname
```

More in [`cml/phase2-router_configs_R1-R4/extra_validations/`](../../../cml/phase2-router_configs_R1-R4/extra_validations/).

---

## Results

Valid runs: `20261010_155902_098180` → `20261010_155911_932381` (9 runs, 36 device backups, 100% success, HTTP 200).

| Workers | Runs | Average | Median | Std. dev. | Min | Max |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 3 | **1.959 s** | 1.937 s | 0.206 s | 1.764 s | 2.175 s |
| 2 | 3 | **0.978 s** | 0.985 s | 0.028 s | 0.947 s | 1.002 s |
| 4 | 3 | **0.497 s** | 0.494 s | 0.012 s | 0.487 s | 0.510 s |

| Workers | Speedup | Efficiency | Per-device mean |
|---:|---:|---:|---:|
| 1 | 1.00× | 100.0% | 0.488 s |
| 2 | 2.00× | 100.1% | 0.481 s |
| 4 | 3.94× | 98.6% | 0.484 s |

### Payload (4 devices, identical in every run)

| Metric | Total |
|---|---:|
| `raw_body_bytes` — raw HTTP response body | 21,165 B |
| `native_json_bytes` — pretty-printed JSON backup | 22,673 B |
| Lines in saved backups | 1,115 |

---

## Findings

- **Fastest method in the project** per device (~0.48 s) and ~41–43% faster than NETCONF/YANG at every worker level.
- The advantage is **not** payload size — the raw JSON body is ~2% *larger* than the raw NETCONF XML. It comes from the rest of the stack: one HTTPS request with no NETCONF session/hello exchange vs SSH + NETCONF session setup.
- Per-device latency is flat across concurrency levels and scaling is essentially linear (98.6% at 4 workers).
- Environment-specific result — do not generalize to "RESTCONF is always faster". Testing `requests.Session()` connection reuse and async HTTP clients are listed in the [roadmap](../../../docs/lessons-learned.md#roadmap).

---

## Output

```text
backups/phase2/restconf/<run_id>/R1.json … R4.json
results/phase2/restconf/<run_id>/results.csv      # run_id = YYYYMMDD_HHMMSS_ffffff
```

CSV columns: `run_id, method, workers, repetition, device, host, duration_s, success, http_status, native_json_bytes, raw_body_bytes, lines, error`.

> The first three run folders (`20261010_155833…` – `20261010_155837…`) are a preliminary single-run pass and are not part of the 3-run dataset.
