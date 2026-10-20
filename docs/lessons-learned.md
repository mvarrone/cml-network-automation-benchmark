# Lessons Learned, Conclusions and Roadmap

[← Back to main README](../README.md)

## Lessons Learned

### Performance

1. **Concurrency dramatically reduces total wall time** for I/O-bound network automation (~7× at 10 sessions in Phase 1).
2. **The concurrency mechanism alone does not explain performance.** Library, transport, framework initialization and protocol behaviour all matter.
3. **Scrapli + AsyncSSH + asyncio produced the lowest Phase 1 wall time** in this specific IOSv workload.
4. **Nornir added orchestration abstractions without an obvious performance penalty.**
5. **pyATS + Unicon is heavier than a simple SSH wrapper** but provides a much richer testing and automation framework.
6. **Per-device latency and total batch wall time are different metrics** and must be reported separately.
7. **NETCONF/YANG and RESTCONF both scaled almost linearly** from one to four workers.
8. **RESTCONF showed ~41–43% lower wall time than NETCONF/YANG** in the four-router CSR1000v lab — an environment-specific result, not a universal protocol rule.
9. **Host memory became the lab scaling constraint** before the automation code did.

### Benchmark hygiene

10. **Framework defaults can distort benchmarks.** Unicon disconnect waits and initialization behaviour had to be controlled explicitly.
11. **Read-only benchmark tools must not modify device configuration** (Unicon's default `init_config_commands`).
12. **Python environment placement matters under WSL** — a venv under `/mnt/c` caused ~16 s imports.

### Compatibility

13. **Legacy IOSv SSH algorithms require explicit compatibility handling** in every SSH stack.
14. **The newest package release is not always the most compatible** with old network operating systems (Paramiko 5.0.0, newer Scrapli).
15. **Local module names can shadow installed packages** and break imports.

### Architecture

16. **Legacy NETCONF and NETCONF/YANG are architecturally different** despite sharing a name: CLI text in XML vs a real YANG data tree.
17. **Modern IOS XE exposes the same YANG model through both NETCONF and RESTCONF**, making a clean protocol comparison possible.

---

## Overall Conclusion

The project evolved from a sequential-vs-concurrent SSH backup experiment into a two-phase study of traditional and model-driven Cisco automation.

**Phase 1 (10 × IOSv):** sequential SSH is simple but slow; explicit threads and `ThreadPoolExecutor` give large gains with little complexity; Nornir adds orchestration at no visible cost; Scrapli + AsyncSSH + asyncio was fastest; pyATS + Unicon is heavier but much richer; legacy NETCONF scales well but exposes a CLI-oriented data model.

**Phase 2 (4 × CSR1000v):** both NETCONF/YANG (TCP/830, XML) and RESTCONF (HTTPS/443, JSON) retrieved the same IOS XE native model and scaled almost linearly; RESTCONF was ~41–43% faster even though its raw body was slightly larger, so the difference reflects the full protocol/software stack rather than payload size.

The main takeaway is that automation performance depends on the **complete execution environment**:

```text
framework + transport + protocol + session establishment + serialization format
+ concurrency model + initialization behaviour + Python version + operating system
+ filesystem placement + device platform + device control plane + CML host resources
```

---

## Roadmap

| Area | Idea |
|---|---|
| Result aggregation | One script that reads every `results.csv` and produces means, medians, std. dev., confidence intervals, speedup and efficiency |
| Visualization | Wall time / speedup / efficiency vs concurrency, best-of-Phase-1, NETCONF vs RESTCONF, per-device latency distributions, payload sizes |
| Resource monitoring | Correlate runs with Windows host, CML VM and per-node CPU/memory to separate stack overhead from host saturation |
| Interleaved runs | Randomize method and worker order to reduce warm-up and temporal-load effects |
| Larger topologies | Re-run Phase 2 with 8 / 16 / 32 IOS XE nodes on a bigger host |
| Session reuse | Persistent NETCONF sessions and `requests.Session()` to separate setup cost from steady-state request cost |
| Write operations | NETCONF `<edit-config>`, RESTCONF `PATCH`/`PUT`, validation and rollback |
| Operational data | Interfaces, routing tables, LLDP neighbours, platform and CPU/memory state |
| More frameworks | Ansible, Cisco NSO, gNMI/OpenConfig, async HTTP clients for RESTCONF, async NETCONF clients |
| Centralized AAA | Replace local credentials with TACACS+ / RADIUS |
