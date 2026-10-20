# Phase 1 — Legacy NETCONF with ncclient

[← Phase 1 overview](../README.md) · [← Main README](../../../README.md)

| | |
|---|---|
| Library | ncclient 0.7.1 + lxml 6.1.3 |
| Concurrency | `ThreadPoolExecutor` |
| Transport | NETCONF over the SSH subsystem on **TCP/22** |
| Device feature | `netconf ssh` (legacy Cisco NETCONF — not `netconf-yang`) |
| Targets | 10 × IOSv (R1–R10) |
| Workers tested | 1, 2, 4, 5, 10 |
| Script | [`netconf_benchmark.py`](netconf_benchmark.py) |
| R1 smoke test | [`test_r1_netconf.py`](test_r1_netconf.py) |

IOSv 15.9(3)M12 has no NETCONF/YANG or RESTCONF, but it does implement Cisco's older NETCONF. This method retrieves the running config over that protocol and bridges toward the model-driven work in [Phase 2](../../phase2/README.md).

---

## How It Works

```python
connection = manager.connect(
    host=host, port=22,
    username=username, password=password,
    hostkey_verify=False, allow_agent=False, look_for_keys=False,
    timeout=15,
)
response = connection.get_config(source="running")
config = extract_cli_config(response.xml)
```

The reply does **not** contain a YANG data tree. It wraps classic IOS CLI text in a single element, which is extracted with an XPath and saved as `.cfg`:

```xml
<rpc-reply>
  <data>
    <cli-config-data-block>
      ! ...plain "show running-config" text...
    </cli-config-data-block>
  </data>
</rpc-reply>
```

```python
root.xpath("//*[local-name()='cli-config-data-block']")
```

### Advertised capabilities

```text
urn:ietf:params:netconf:base:1.0
urn:ietf:params:netconf:capability:writeable-running:1.0
urn:ietf:params:netconf:capability:startup:1.0
urn:ietf:params:netconf:capability:url:1.0
urn:cisco:params:netconf:capability:pi-data-model:1.0
urn:cisco:params:netconf:capability:notification:1.0
```

Only NETCONF base 1.0 — no YANG library, no `:validate`, no `:xpath`.

---

## Running

```powershell
# optional: session + capabilities + get-config on R1
python .\src\phase1\netconf\test_r1_netconf.py
```

```python
MAX_WORKERS = 10   # 1, 2, 4, 5, 10
```

```powershell
python .\src\phase1\netconf\netconf_benchmark.py
```

Router side: `netconf ssh` must be configured (included in the [Phase 1 bootstrap configs](../../../cml/phase1-router_configs_R1-R10/)).

---

## Results

| Workers | Avg wall time | Self-speedup | Efficiency | Per-device mean |
|---:|---:|---:|---:|---:|
| 1 | 10.587 s | 1.00× | 100% | 1.057 s |
| 2 | 5.617 s | 1.88× | 94.2% | 1.106 s |
| 4 | 3.550 s | 2.98× | 74.6% | 1.225 s |
| 5 | 2.753 s | 3.85× | 76.9% | 1.308 s |
| 10 | **1.745 s** | 6.07× | 60.7% | 1.588 s |

Speedup vs Netmiko sequential at 10 workers: **7.01×**. No failed backups.

---

## Findings

- Performance is on par with the threaded SSH CLI methods — unsurprising, since it is still one SSH session per device returning the same text.
- Architecturally it is very different from [NETCONF/YANG](../../phase2/netconf_yang/README.md): the "data model" is just CLI text in XML, so you gain a structured RPC envelope but not structured configuration data.
- Two size metrics are recorded: `bytes` (extracted CLI text) and `raw_xml_bytes` (full RPC reply).
- Uses Paramiko under the hood, so the same **Paramiko 4.0.0** pin applies for the legacy SSH algorithms.

---

## Output

```text
backups/phase1/netconf/<run_id>/R1.cfg … R10.cfg
results/phase1/netconf/<run_id>/results.csv
```

CSV columns: `run_id, method, workers, device, host, duration_s, success, bytes, raw_xml_bytes, lines, error`.
