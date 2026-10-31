# MSI Dragon Center — Reverse-Engineering Notes

**English** | [简体中文](README.zh-CN.md)

Unofficial, independent reverse-engineering notes on the communication architecture of
**MSI Dragon Center 2.x**, written while evaluating whether a lightweight open-source
control tool (in the spirit of GHelper) could replace it on a 2019 MSI GS65 Stealth 9SE.

> This repository contains **no MSI binaries, drivers, installers, power-scheme files,
> or extracted code/strings**. It documents functional, interoperability-relevant facts
> (WMI class names, EC register offsets, power-plan GUIDs, protocol framing) that were
> independently derived from a locally owned installation. See [NOTICE.md](NOTICE.md)
> before using or redistributing anything here.

---

## What is in here

| Document | Language | Contents |
|---|---|---|
| [Architecture notes](docs/en/01-architecture.md) | EN | Three-tier architecture, named-pipe protocol, WMI/EC/power-plan access, feature analysis, implementation guidance |
| [EC register map](docs/en/02-ec-register-map.md) | EN | Model-specific EC offsets calibrated on a GS65 Stealth 9SE (MS-16Q4) |
| [Artifact inventory](docs/en/03-artifacts.md) | EN | What the local dump artifacts are, how they were produced, and why they are not published |
| [架构分析（中文原文）](docs/zh/01-architecture.md) | 中文 | Chinese original of the architecture notes |
| [EC 寄存器表（中文）](docs/zh/02-ec-register-map.md) | 中文 | Chinese version of the register map |
| [逆向产物说明（中文）](docs/zh/03-artifacts.md) | 中文 | Chinese version of the artifact inventory |
| [tools/](tools/) | EN | Original helper scripts for .NET metadata / string / IL extraction |

The reverse-engineering **probe and control programs** used to calibrate the EC are
deliberately **not included** in this repository. The documents record only their
findings, so the notes remain useful without distributing the tooling.

---

## Key findings

1. **Dragon Center is a three-tier system.** The WPF UI never touches hardware; it sends
   encrypted JSON over the named pipe `\\.\pipe\MSI_SERVICE_2` to the SYSTEM service
   `MSIAPService.exe` (`msiservice`), which is the only component that talks to the EC,
   ACPI WMI, and the registry.
2. **Performance modes are Windows power plans.** The "System Environment Setting"
   presets map to power-scheme GUIDs; `MSIECO.dll` imports `.eps` hives and switches the
   active scheme through `powrprof.dll`. This layer is pure Windows and easy to reproduce.
3. **Fan and battery control use two paths:** ACPI WMI classes under `root\WMI`
   (`MSI_System`, `MSI_Power`, `MSI_Master_Battery`, …) and direct EC RAM access through
   the WinIo driver on ports `0x62`/`0x66`.
4. **EC offsets are model-specific.** On the GS65 9SE (MS-16Q4) the working offsets for
   temperature, fan duty, fan mode, cooler boost, battery threshold, and manual fan
   curves were calibrated by differential EC dumps. See the [register map](docs/en/02-ec-register-map.md).
5. **A standalone reimplementation is feasible and preferable** to reusing the abandoned
   official service: MSI's lower layers are standard ACPI EC, standard WMI, and standard
   Windows power plans.

---

## Repository layout

```
RE_repository/
├── README.md                  # this file (EN)
├── README.zh-CN.md            # Chinese README
├── NOTICE.md                  # legal / copyright / trademark notice
├── CONTRIBUTING.md            # contribution rules (no proprietary artifacts)
├── LICENSE                    # MIT — original code and tooling
├── LICENSE-docs               # CC BY 4.0 — original documentation
├── docs/
│   ├── en/                    # English documents
│   └── zh/                    # Chinese documents (originals / translations)
└── tools/                     # original .NET metadata / string / IL dump scripts
```

---

## Reproducing the analysis

You need your **own legally obtained** copy of the software and Python 3.9+.

```bash
pip install dnfile dncil pefile

# Dump .NET metadata (types, fields, methods, P/Invoke, enums)
python tools/dump_dotnet.py "path/to/YourAssembly.exe"

# Extract ASCII + UTF-16LE strings
python tools/strings_extract.py "path/to/YourAssembly.exe"

# Disassemble IL for methods whose full name matches a substring
python tools/il_dump.py "path/to/YourAssembly.exe" "FanSettings" fan_il.txt
```

The first two scripts write their output to the current directory; `il_dump.py` writes
to the path you pass. Do not publish those outputs: they reproduce metadata and code
from a proprietary binary.

For EC calibration, the standard differential-dump method is described in
[Architecture notes §7.3](docs/en/01-architecture.md#73-deriving-ec-register-offsets-by-differential-dump).
A generic EC dump and register-diff workflow is enough; no proprietary component is
required beyond the driver you choose to load.

---

## Prior art and related work

The MSI EC layout has been studied by several open-source projects (for example
`msi-ec`, `MControlCenter`, and `isw`). Their published register tables are useful
cross-checks. This repository's GS65-specific values were calibrated independently and
are presented as observations, not as a specification.

---

## Authorship and AI assistance

The **writing, translation, and editing** of the reverse-engineering content in this
repository was carried out with the participation of **DeepSeek v4 Flash** and
**DeepSeek v4 Pro**. The human author (hugugiko) designed the analysis, performed and
verified the technical work against the binary and runtime evidence, and remains
responsible for the published content. This disclosure does not imply any endorsement by
DeepSeek.

---

## Legal

This is **unofficial research**, not affiliated with or endorsed by Micro-Star
International (MSI). "MSI", "Dragon Center", and related marks belong to their owners
and are used here only to identify the software under study. No MSI code or binaries are
redistributed. Reverse engineering may be restricted by the software's EULA and by local
law; you are responsible for assessing that before using or contributing to this
material. **Read [NOTICE.md](NOTICE.md).**

Nothing here is legal advice.

---

## License

- Original **code and scripts**: [MIT](LICENSE)
- Original **documentation**: [CC BY 4.0](LICENSE-docs)

Copyright (c) 2026 hugugiko.
