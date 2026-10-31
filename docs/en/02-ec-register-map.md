# EC Register Map — MSI GS65 Stealth 9SE (MS-16Q4)

**English** | [简体中文](../zh/02-ec-register-map.md)

> **Scope.** This is a **model-specific observation table**, calibrated on one machine.
> It is not an MSI specification and it is not guaranteed to apply to other models or
> firmware revisions.
>
> **Source of the data.** The values were obtained by reading and writing the embedded
> controller at runtime with a private calibration tool. The tool's source code and
> binaries are **not distributed in this repository**; only the resulting
> interoperability facts are documented here.
>
> **Risk.** Writing EC registers can alter thermal limits, fan behavior, charging
> behavior, and other firmware-managed state. An incorrect write can cause instability
> or hardware damage. Use at your own risk. See [NOTICE.md](../../NOTICE.md).

---

## 1. Target machine

| Item | Value |
|---|---|
| Model | MSI GS65 Stealth 9SE |
| Mainboard | MS-16Q4 |
| EC firmware | `16Q4EMS1.1100712` |
| BIOS | `E16Q4IMS.118` |
| EC access | WinIo driver (`WinIo64.sys`), I/O ports `0x62`/`0x66` |
| EC access commands | read `0x80`, write `0x81` (WinIo wrapper command codes) |
| OS used for calibration | Windows 11 |

The ACPI WMI interface (`root\WMI`, `MSI_*` classes) exists on this machine but behaved
unreliably in testing (apparent firmware bugs), so direct EC access was used for the
fan, temperature, and battery values below.

---

## 2. Read registers

| Offset | Meaning | Observed value | Status |
|---|---|---|---|
| `0x68` | CPU temperature (°C) | e.g. 62, follows load | ✅ verified |
| `0x80` | GPU temperature (°C) | e.g. 64 | ✅ verified |
| `0x71` | CPU fan current duty (raw) | 60 → 70 under load | ✅ verified |
| `0x89` | GPU fan current duty (raw) | e.g. 70 | ✅ verified |
| `0xEF` | Battery charge threshold | `0xE4` = charge to 100% | ✅ verified |
| `0xA0` | EC firmware version string (16 bytes) | `16Q4EMS1.1100712` | ✅ verified |
| `0xF4` | Fan mode | see §3 | ✅ verified |
| `0xD4` | Fan-related, purpose not fully determined | `0x70` | 🔵 candidate |
| `0xF2` | Performance mode, purpose not fully determined | `0x80` | 🔵 candidate |

Registers observed to change during normal operation (temperatures and fan activity):
`0x68`, `0x71`, `0x89`, `0xC8`, `0xC9`, `0x99`, `0x9B`, `0xCB`, `0xCD`, `0xF9`.

RPM can be computed from a period register:

| Fan | Period register | Formula |
|---|---|---|
| CPU | `0xCC` | `RPM = 478000 // value` |
| GPU | `0xCA` | `RPM = 478000 // value` |

> `//` denotes integer division. Guard against a zero value.

---

## 3. Fan control

Duty percentage is **positive**: a larger value means a faster fan. An earlier
observation of the opposite relationship was traced to reading unrelated registers that
were perturbed by Cooler Boost (`0x01`, `0x02`, …) and was retracted.

### 3.1 Fan mode — `0xF4`

| Value | Mode |
|---|---|
| `0x0C` | Auto |
| `0x4C` | Basic |
| `0x8C` | Advanced (manual curve active) |

> The values actually calibrated on this machine are `0x0C`/`0x4C`/`0x8C`. Public
> `msi-ec`/`isw` tables list `0x0D`/`0x4D`/`0x8D` for some models; do not assume the two
> are interchangeable. Verify on your own hardware.

### 3.2 Cooler Boost — `0x98`

| Value | State |
|---|---|
| `0x00` | Off |
| `0x80` | On (fans at maximum) |

### 3.3 Manual fan curve (Advanced mode)

| Fan | Temperature thresholds | Duty percentages |
|---|---|---|
| CPU | `0x6A`–`0x6F` | `0x72`–`0x78` |
| GPU | `0x82`–`0x87` | `0x8A`–`0x90` |

The curve is a six-point temperature → duty polyline, matching the six threshold bytes.
The duty ranges as documented during calibration span seven addresses; exactly which one
is a mode/header byte versus a curve point should be re-verified with a differential dump
before relying on the last byte.

---

## 4. Battery

- **Read:** `0xEF` holds the charge-stop threshold. `0xE4` corresponds to "stop at 100%".
- **Write (unverified):** the working hypothesis is `value = percent + 0x80`, i.e. 100%
  → `0xE4` (228), 80% → `0xD0` (208). This was implemented in the private tool but had
  not been confirmed on hardware at the time of writing. Validate with a differential
  dump before use.
- Quick Charge 3.0 (USB fast charging) is a separate feature and is not controlled by
  this register.

---

## 5. Calibration method

1. Load the EC-access driver as administrator.
2. Dump the full EC range `0x00`–`0xFF` as a baseline.
3. Change exactly one setting in the official application (for example, fan from Auto to
   Advanced, or the charge threshold from 100% to 80%).
4. Dump again and diff the two images.
5. Repeat with the setting toggled back and forth to separate real targets from noise.
6. Record only offsets that reproduce consistently, and label them with model, EC
   firmware, and BIOS version.

This is the same differential method used by GHelper and other vendor-control projects.
Because EC layouts vary by model, treat every offset as model-scoped.

---

## 6. Cross-checks and prior art

The following open-source projects publish MSI EC layouts and are useful for comparison.
Their register tables may differ by model and firmware:

- `msi-ec` (Linux kernel module)
- `MControlCenter` (MCC)
- `isw`

Agreement with those projects increases confidence; disagreement is not automatically an
error on either side, because the layout is model-specific.

---

## 7. Summary of verification status

| Capability | Status |
|---|---|
| Read CPU/GPU temperature | ✅ verified |
| Read CPU/GPU fan duty | ✅ verified |
| Read battery threshold | ✅ verified |
| Switch Windows power plan | ✅ verified |
| Read/write arbitrary EC registers | ✅ verified |
| Cooler Boost (`0x98 = 0x80`) | ✅ verified |
| Manual fixed fan duty (`0xF4 = 0x8C` + curve) | ✅ verified |
| Write battery threshold (`0xEF = percent + 0x80`) | 🟡 implemented, not hardware-verified |
| Import MSI `.eps` power schemes | ✅ verified (see architecture notes §4.3) |
