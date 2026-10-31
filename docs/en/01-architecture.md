# MSI Dragon Center — Architecture and Reverse-Engineering Notes

**English** | [简体中文](../zh/01-architecture.md)

> **Purpose.** Understand how MSI's official Dragon Center control software communicates,
> so that a lightweight open-source replacement in the spirit of GHelper can be built.
>
> **Subject.** A complete local backup of a Dragon Center 2.x installation directory
> (referred to below as `DC_BACKUP/`). The analysis was performed on the authors' own
> machine and software copy.
>
> **Evidence labels**
> - ✅ **Verified from the binary** — directly confirmed by strings, metadata, or IL
>   disassembly.
> - 🟡 **Structural inference** — derived from type and method names and their call
>   relationships; no plaintext constant was observed.
> - 🔵 **Model-dependent, requires runtime probing** — EC register offsets and similar
>   values differ by model and must be measured on the target machine.
>
> This document contains no MSI code, binaries, or extracted data. It records functional
> facts for interoperability only. Read [NOTICE.md](../../NOTICE.md) first.

---

## 1. Overall conclusion (TL;DR)

Dragon Center is not a single program. It is a **three-tier client/server system**:

```
┌─────────────────────────────────────────────────────────────────────┐
│  UI tier (user session, standard privileges)                        │
│  Dragon Center.exe / CommandCenter_Start.exe / GameCenter-OC.exe    │
│  gpuControl.exe / AI Wizard.exe ... (all .NET WPF applications)     │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ named-pipe IPC (3DES-encrypted JSON)
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Service tier (user session, SYSTEM privileges)                     │
│  MSIAPService.exe (service name "msiservice", always running)       │
│  — the single hardware-access gate; the UI cannot touch hardware    │
└───────┬──────────────────┬──────────────────────┬───────────────────┘
        │ WinIo driver     │ WMILib.dll (COM)     │ registry
        ▼                  ▼                      ▼
┌──────────────┐  ┌──────────────────────┐  ┌──────────────┐
│ Embedded     │  │ ACPI WMI (root\WMI)  │  │ HKLM etc.    │
│ Controller   │  │ MSI_System/Power/... │  │ config /     │
│ ports 0x62,  │  │ MSI_Master_Battery   │  │ licensing    │
│ 0x66         │  └──────────────────────┘  └──────────────┘
│ (RAM access) │
└──────────────┘
```

**Three facts that determine the whole design:**

1. ✅ **UI processes do not access hardware directly.** Every EC, fan, and battery
   operation is sent to the named pipe `\\.\pipe\MSI_SERVICE_2`, where
   `MSIAPService.exe` translates it into EC, WMI, or registry calls. This means you can
   either bypass the official UI and talk to that pipe yourself (**path A**), or replace
   the three things the service does (**path B**).

2. ✅ **MSI's "performance modes" are Windows power plans.** Balanced, Performance,
   Movie, Battery Saver, and Custom correspond to a set of power-scheme GUIDs (see the
   appendix) and are switched through `powrprof.dll`'s `PowerSetActiveScheme`. This
   differs from ASUS, where most modes go through ACPI WMI / ATKACPI.

3. ✅ **Fan, battery-charge-threshold, and EC register access use two paths:** **ACPI
   WMI** (the `MSI_System`, `MSI_Master_Battery`, etc. classes under `root\WMI`) and
   **direct EC RAM access** (WinIo driver plus ports `0x62`/`0x66`).

---

## 2. Component inventory

| File | Type | Role (reverse-engineered) |
|---|---|---|
| `Dragon Center.exe` | .NET WPF | **Main UI plus most business logic.** Fan curves, battery, performance modes, and WMI/EC wrappers live here. Its IL is obfuscated/encrypted. |
| `MSIAPP_Service/MSIAPService.exe` | .NET service | **Hardware-access service** (not obfuscated; fully disassembled). Named-pipe server plus WinIo, WMI, and registry bridge. |
| `MSIAPP_Service/WMILib.dll` | Native C++ (COM) | WMI COM wrapper exporting `ReadWMI`, `ReadWMIAll`, and `WriteWMI`. |
| `MSIAPP_Service/WinIo32/64.dll + .sys` | Native driver | **WinIo kernel driver**, providing `GetPortVal`, `SetPortVal`, `GetPhysLong`, and `SetPhysLong` for port and physical-memory I/O. |
| `MSIECO.dll` | .NET | **"ECO performance mode" module** (not obfuscated; fully disassembled). Maps modes to Windows power plans. |
| `MSIECO/*.eps` | Registry hive files | Power-scheme export files (`regf` format), imported through `PowerImportPowerScheme`. |
| `MsiHid.dll` | Native | HID access (Fn keys, SteelSeries keyboard, special keys). |
| `UEFIVaribleDll.dll` | Native | UEFI NVRAM variable access (BIOS settings such as Fn/Win swap). |
| `IntelOverclockingSDK.dll` | Native | Intel XTU SDK (CPU overclocking/undervolting inside "Custom" mode). |
| `gpuControl.exe` | .NET | GPU overclocking (NVAPI / `nvpowerapi.dll`, core and VRAM clock offsets). |
| `GameCenter-OC.exe` | .NET | Game center plus the CPU-core overclocking entry point (through `IntelOverclockingSDK`). |
| `ProfileHelperModel.dll` | .NET | User "Profile" data model. |
| `AsyncSocketLib.dll` / `NamedPipeClientLib.dll` | .NET | Mobile-device connectivity / named-pipe client used by the official UI. |
| `devcon.exe` | Native | Driver install/uninstall utility (used to install `WinIo64.sys`). |

> 🟡 The three features of interest — **performance modes, fan, and battery** — do **not**
> require `IntelOverclockingSDK`, `gpuControl`, or `MsiHid`. They involve only the EC,
> WMI, and power plans, which is good news for a lightweight replacement.

---

## 3. IPC protocol (UI ↔ service) ✅ Fully recovered

### 3.1 Named pipe

- Pipe name: `\\.\pipe\MSI_SERVICE_2` ✅
- Service name: `msiservice` (`MSIAPService.exe`, running as SYSTEM) ✅
- Pipe type: `PIPE_TYPE_MESSAGE` (message mode). Security descriptor:
  `D:(A;OICI;GRGW;;;AU)(A;OICI;GA;;;BA)` (Authenticated Users plus Administrators). ✅

### 3.2 Encryption

Payloads are not plaintext. They use **3DES (TripleDES) with an MD5-derived key**: ✅

- `System.Security.Cryptography.MD5CryptoServiceProvider` and
  `TripleDESCryptoServiceProvider`.
- The key is derived with MD5 from a raw string sent by the client during the handshake
  (method name `GetClientRawStringForKeyGeneration`).
- Consequence: reusing the official service requires reproducing the handshake to obtain
  the derived key. This is one reason that reimplementing the hardware access (path B) is
  simpler.

### 3.3 Request frames (client → service, prefix plus JSON)

| Prefix | Meaning | Notes |
|---|---|---|
| `HS` | Handshake | Handshake / key negotiation |
| `RMREQ` | Read Memory Request | Read EC RAM (physical memory or port) |
| `WMREQ` | Write Memory Request | Write EC RAM |
| `RPREQ` | Read Port Request | Read an I/O port |
| `WPREQ` | Write Port Request | Write an I/O port |
| `EVTWREQ` | Event Write Request | WMI event write |
| (registry) | Read/Write Registry | JSON carries `root`, `keyName`, `valueName`, `value` |

### 3.4 Response frames (service → client)

| Prefix | Meaning |
|---|---|
| `HS:ACK:` / `HS:ERR:` | Handshake success / failure |
| `IO:RMRST:` / `IO:WMRST:` | Read / write memory response |
| `IO:RPRST:` / `IO:WPRST:` | Read / write port response |
| `IO:ERR:` | I/O error |
| `REG:RRST:` / `REG:WRST:` / `REG:ERR:` | Registry read / write / error |
| `WMI:RRST:` / `WMI:WRST:` / `WMI:EVTWRST:` / `WMI:ERR:` | WMI read / write / event / error |

JSON keys observed: `WMIValue`, `RegistryValue`. A WMI item is a `property`/`value`
pair; a registry item is `root`/`keyName`/`valueName`/`value`. ✅

### 3.5 Service-side hardware bridge (`MSIAPService.WinIO` / `.WMI`) ✅

The service contains two kinds of P/Invoke wrapper:

- `WinIO` class: fields `EC_Ram_Address`, `EC_HIGH`, `EC_LOW`, `EC_DATA`; methods
  `readECRam`, `ReadPort`, `WritePort`, `ReadMemory`, `WriteMemory`, `checkBackDoor`.
- `WMI` class: `readWMI`, `readWMIAll`, `writeWMI` (forwarded to `WMILib.dll`).

> 🔵 The concrete port numbers for `EC_HIGH`/`EC_LOW`/`EC_DATA` exist as `ldc.i4`
> constants in `.cctor`, but the IL is obfuscated and no plaintext value was recovered.
> Following the ACPI EC convention used by every x86 laptop, they are expected to be
> **0x66 (command/status)** and **0x62 (data)**. All open-source MSI EC tools
> (`MControlCenter`, `msi-ec`) use those ports.

---

## 4. Hardware-access layer

### 4.1 ACPI WMI (MSI's "universal bus") ✅ Fully recovered

This is the most important and most directly reusable finding. MSI firmware exposes an
ACPI WMI interface in the `root\WMI` namespace:

| WMI class | Method/property | Purpose (inferred) |
|---|---|---|
| `MSI_System` | method `System` | **System state: fan RPM, temperatures, mode flags** |
| `MSI_Power` | property `Power` | **Power/performance mode (User Scenario)** |
| `MSI_Device` | method `Device` | Device switches (Wi-Fi/Bluetooth/camera, etc.) |
| `MSI_Software` | method `Software` | Software-level control |
| `MSI_CPU` | property `CPU` | CPU information/temperature |
| `MSI_VGA` | property `VGA` | GPU information/temperature |
| `MSI_AP` | property `AP` | AP (access point) related |
| `MSI_Master_Battery` | property `Master_Battery` | **Battery Master (charge threshold)** |
| `MSI_Event` | — | **Event notifications** (Fn mode switch, ECO events) |

WQL examples taken from binary strings: ✅

```
SELECT * FROM MSI_System
SELECT * FROM MSI_Device
SELECT Power FROM MSI_Power
SELECT CPU FROM MSI_CPU
SELECT VGA FROM MSI_VGA
SELECT Master_Battery FROM MSI_Master_Battery
SELECT * FROM MSI_Event
```

Call formats used by the client wrapper: ✅

```
Read (Query):  root\WMI:Q:MSI_System:System:
Write (Set):   root\WMI:S:MSI_...
```

**A replacement tool can therefore use the standard `System.Management`
(`ManagementObject` / `InvokeMethod`) API to read and write these WMI classes without the
official service.** This is the core of path B.

### 4.2 Direct EC access 🔵

- The WinIo driver performs `GetPortVal`/`SetPortVal` on ports **0x66 (command)** and
  **0x62 (data)**, implementing standard ACPI EC reads and writes.
- `readECRam` means "write an EC register offset to 0x66, then read or write data
  through 0x62".
- The client also wraps `MSI_App_Service_ReadMemory` / `WriteMemory`, which go through the
  pipe → service → WinIo `ReadMemory`/`WriteMemory`.
- Example: the first step of `BatteryUI::WriteECtoBatteryMode` is a
  `ReadMemory(0xFC0008EF)` (read an EC register, modify bits, write back). 🟡

> 🔵 **EC register offsets (fan-speed address, charge-threshold address, mode bytes) are
> model-specific** and are hidden inside the obfuscated `Dragon Center.exe` IL. The
> correct approach is a runtime EC dump (see §7.3), which is also how GHelper and
> MControlCenter are developed.

### 4.3 Windows power plans (the foundation of performance modes) ✅ Fully recovered

`MSIECO.dll` maps each "system environment setting" preset to a **Windows power-scheme
GUID**:

| Mode | Enum `EnumECOPS` | Power-scheme GUID | Notes |
|---|---|---|---|
| Balance | `MSI_BALANCE` | `EC73D77B-025C-46F2-A867-46F201BE299F` | Custom (MSI Balance.eps), static decode 🟡 |
| Performance | `MSI_PERFORMANCE` | `2C6153B0-5B06-4FF1-9675-014B8E40E355` | Custom (MSI Performance.eps), static decode 🟡 |
| Gaming | `ECO_GAMMING` | `98B32AC9-6345-4AB9-A981-0F0E39C08578` | Gaming.eps ✅ |
| Movie | `ECO_MOVIE` | `A469DC3C-170E-4428-989C-0133582FEC6F` | Movie.eps ✅ (see note) |
| Presentation | `ECO_PRESENTATION` | `C3407F92-A518-430B-94BF-9874575E931E` | Presentation.eps ✅ |
| Office | `ECO_OFFICE` | `DF8734A4-F9A5-49CF-A336-B8F6E6207807` | Office.eps ✅ |
| Turbo Battery | `ECO_TURBOBATTERY` | `DB5648DC-C820-4FD8-B413-2CCCD48C273F` | TurboBattery.eps ✅ |
| Windows Balanced | `BALANCED` | `381B4222-F694-41F0-9685-FF5BB260DF2E` | Windows standard |
| Windows High Performance | `HIGH_PERFORMANCE` | `8C5E7FDA-E8BF-4A96-9A85-A6E23A8C635C` | Windows standard |
| Windows Power Saver | `SAVING` | `A1841308-3541-4FAB-BC81-F71556F20B4A` | Windows standard |

> **Correction (2026-10).** The Movie GUID originally decoded from `MSIECO.dll` IL
> (`0BC57CB5-…`) was later found to be a misdecode. The GUID embedded in the shipped
> `Movie.eps` hive is `A469DC3C-170E-4428-989C-0133582FEC6F` and is authoritative,
> because `.eps` is the file actually imported. The same check confirmed the Gaming,
> Presentation, Office, and Turbo Battery GUIDs listed above.

Switching sequence (methods on `MSIECO.CECO`): ✅

```
SetECOPowerScheme(mode)
  → on first run PowerImportPowerScheme("xx.eps")   import the power plan
  → PowerSetActiveScheme(GUID)                      activate it
ActiveECOPowerScheme()  → PowerGetActiveScheme      read back the active plan
```

> Key conclusion: **"Performance / Balanced / Battery Saver" is effectively a power-plan
> switch**; "Movie", "Gaming", etc. are MSI-customized plans. GHelper mostly uses ACPI
> for ASUS modes, while this MSI layer is pure Windows and is easy to reproduce — even
> with `powercfg /setactive <GUID>`.

---

## 5. The three features

### 5.1 System environment settings (Balanced / Performance / Movie / Battery Saver + Custom) ✅🟡

- **The four presets** call `MSIECO.dll` to switch power plans (§4.3) and also write a
  "current mode" flag to the EC through WMI `MSI_Power`/`MSI_System`, so that Fn-key
  switching and indicator LEDs stay in sync.
- **"Custom mode"** is a user Profile (`ProfileHelperModel`) containing:
  - CPU tuning (`CPU_OverClock` → `IntelOverclockingSDK.dll`, including ratio
    `CPU_Ratio_Index` and voltage) 🟡
  - GPU tuning (`gpuControl.exe` → NVAPI, `Core Clock Offset` / `VRAM Clock Offset`) 🟡
  - fan curve (see §5.2)
  - display/DPI, Nahimic audio, LED, and other miscellaneous settings (out of scope)
- Relevant enums/types: `.ECOModes` (`ECO_GAMMING`/`MOVIE`/`PRESENTATION`/`OFFICE`/
  `TURBOBATTERY`/`ECO_DISABLE`/`BALANCED`/`HIGH_PERFORMANCE`/`SAVING`), `.ShiftType::ECO`,
  and `Shift_Control` ("Shift" is MSI's older name for performance mode).

### 5.2 Fan speed: reading and control ✅🟡

`Dragon_Center.Controls.TuneMgr.SetFunction.FanSettings` is the core of the fan logic:

- **Reading RPM:** WMI `MSI_System` (`SELECT * FROM MSI_System`) returns the current fan
  RPM. UI fields: `CpuFanSpeed` / `GpuFanSpeed` / `Fan3Speed` / `Fan4Speed` (up to four
  fans).
- **Manual control is a six-point polyline** (temperature → fan percentage):
  - CPU fan: `FanCPU1..6Temperature` + `Fan_CPU_Value_1..6`
  - GPU fan: `FanVGA1..6Temperature` + `Fan_VGA_Value_1..6`
- **Fan modes:** `Auto_Fan` / `Basic_Fan` / `Basic_CPU_Fan` / `Basic_VGA_Fan` / `Adv_Fan`,
  plus `Fan_Mode_Value`.
- **Cooler Boost:** the `IsCoolerBoost` switch (fans at maximum).
- **Storage:** 🟡 the field name `TableNotReload_ECRam` indicates that the fan-curve table
  lives in **EC RAM** and is read/written through
  `MSI_App_Service_ReadMemory`/`WriteMemory` (the direct EC path from §4.2).

> 🔵 The EC start address of the fan curve, the size of each point, and the RPM
> conversion formula (usually `RPM = value * 100` or a lookup table) must be calibrated
> with a real-machine dump. The calibrated map for one machine is in
> [02-ec-register-map.md](02-ec-register-map.md).

### 5.3 Battery Master (charge state) ✅🟡

The UI strings (taken from string resources) describe **three charging strategies**: ✅

| Option | Behavior |
|---|---|
| Best for Mobility | Charge to 100% and keep it there |
| Balanced | Start charging below 70%, stop at 80% |
| Best for Battery | Start charging below 50%, stop at 60% |

Implementation uses two paths: ✅🟡

1. **WMI:** `SELECT Master_Battery FROM MSI_Master_Battery` reads the current charge
   state/threshold; writing works through the same path (`SetWMIValue`).
2. **EC:** `BatteryUI::WriteECtoBatteryMode` → `MSI_App_Service_ReadMemory/WriteMemory`
   writes the EC charge-threshold register (the static analysis pointed at addresses
   around `0xFC0008EF`; 🟡 the exact offset needs calibration).

> There is also a separate **Quick Charge 3.0** feature (USB-port fast charging on some
> models), which is unrelated to battery-health management and is controlled through
> `MSI_Device`.

---

## 6. Implementation approach for a GHelper-like tool

### 6.1 Two paths compared

| | Path A: reuse the official service | Path B: independent reimplementation (recommended) |
|---|---|---|
| Principle | Connect to `\\.\pipe\MSI_SERVICE_2` and call ReadMemory/WriteMemory/WMI using 3DES-encrypted JSON | Load a driver for EC access, call WMI directly, and switch power plans directly |
| Pros | No need to deal with driver or EC details | Fully independent, lightweight, open-sourceable, no dependency on an abandoned official component |
| Cons | Depends on the discontinued `msiservice`; must reproduce the 3DES handshake key | Requires administrator rights to load a driver; EC offsets must be dumped per model |
| GHelper analogue | Not recommended | **This is what GHelper does** (it also does not depend on Armoury Crate) |

**Path B is recommended.** The official service is no longer maintained and its protocol
uses a private encrypted handshake, while MSI's lower layers are **standard ACPI EC,
standard WMI, and standard Windows power plans**, all of which have public, reproducible
implementations.

### 6.2 Layered design (path B)

```
┌─────────────────────────────────────────────┐
│  UI layer (WPF / WinUI / Electron, any)     │
│  - mode buttons (balanced/performance/...)  │
│  - fan-curve editor + Cooler Boost          │
│  - three battery-threshold presets          │
│  - live RPM / temperature / power monitor   │
└──────────────────────┬──────────────────────┘
                       │
┌──────────────────────▼──────────────────────┐
│  Control core (C#/.NET is easiest;          │
│  System.Management is built in)             │
│  ┌─────────────┐ ┌──────────┐ ┌────────────┐│
│  │ EC access   │ │ WMI      │ │ Power plan ││
│  │ (WinIo/     │ │ root\WMI │ │ powercfg / ││
│  │ inpout,     │ │ MSI_*    │ │ PowerSet-  ││
│  │ 0x62/0x66)  │ │          │ │ ActiveScheme││
│  └─────────────┘ └──────────┘ └────────────┘│
└─────────────────────────────────────────────┘
```

### 6.3 Concrete actions per feature

| Feature | Read (monitor) | Write (control) |
|---|---|---|
| Performance mode | `PowerGetActiveScheme` / WMI `MSI_Power` | `PowerSetActiveScheme(GUID)` plus write the mode byte through WMI `MSI_Power`/`MSI_System` |
| Fan speed | WMI `SELECT * FROM MSI_System` (RPM), or read the EC RPM register | Write the EC fan-curve table and fan-mode byte; `IsCoolerBoost` |
| Battery threshold | WMI `SELECT Master_Battery FROM MSI_Master_Battery` | Write WMI `MSI_Master_Battery` plus the EC charge-threshold register |

### 6.4 Key difficulties and mitigation

1. **EC register offsets are unknown and model-specific** → use a **runtime EC dump**:
   enumerate EC `0x00`–`0xFF`, record which bytes change before and after changing a fan,
   mode, or battery setting, and infer the offsets. Open-source references such as
   `MControlCenter` (MCC) and the Linux `msi-ec` module have documented EC layouts for
   many MSI models and are useful cross-checks.
2. **Driver privileges** → reuse `WinIo64.sys` (present in `DC_BACKUP/`) or `inpout32`;
   it only needs to be installed once. `RWEverything`/`WinRing0` are alternatives.
3. **WMI method parameters** → enumerate properties and methods directly with
   PowerShell's `Get-WmiObject -Namespace root\WMI -Class MSI_System`; this is faster and
   more accurate than disassembly (see §7.2).

---

## 7. Practical handbook

### 7.1 Quickly validate WMI (verify the hardware interface in 30 seconds)

```powershell
# Enumerate MSI ACPI WMI classes
Get-WmiObject -Namespace root\WMI -List | Where-Object { $_.Name -like 'MSI_*' }

# Read system/fan data
Get-WmiObject -Namespace root\WMI -Class MSI_System | Format-List *
Get-WmiObject -Namespace root\WMI -Query "SELECT * FROM MSI_System"

# Read battery
Get-WmiObject -Namespace root\WMI -Query "SELECT Master_Battery FROM MSI_Master_Battery"

# Read power mode
Get-WmiObject -Namespace root\WMI -Query "SELECT Power FROM MSI_Power"
```

### 7.2 Infer WMI method signatures with PowerShell

```powershell
$c = Get-WmiObject -Namespace root\WMI -Class MSI_System
$c.GetType().GetMethods()          # list methods
$c | Get-Member                    # list properties
# To invoke a method:
Invoke-WmiMethod -Namespace root\WMI -Class MSI_System -Name System -ArgumentList ...
```

### 7.3 Deriving EC register offsets by differential dump

1. Load `WinIo64.sys` as administrator and write a minimal EC reader/writer
   (`out 0x66, idx; in 0x62`).
2. Dump the full EC range `0x00`–`0xFF` to a file.
3. In the official Dragon Center, change one state — for example, fan from 30% to 100%,
   or battery charging from "100%" to "80%".
4. Dump again and `diff` the two files. The changing bytes are the target registers.
   Repeat several times to confirm.
5. Put the resulting offsets into your tool and maintain a per-model whitelist, the way
   GHelper maintains machine profiles.

### 7.4 Equivalent calls for the official service internals

| Official internal call | Your equivalent |
|---|---|
| `WinIO.GetPortVal/SetPortVal` | `GetPortVal/SetPortVal` after loading `WinIo64.sys` yourself |
| `WinIO.readECRam` | Standard EC sequence: `out 0x66, addr; ... ; in 0x62` |
| `WMILib.ReadWMI/WriteWMI` | `System.Management` `ManagementObject` |
| `MSIECO.SetECOPowerScheme` | `powercfg /setactive <GUID>` or P/Invoke `PowerSetActiveScheme` |

---

## 8. Appendix

### 8.1 Named-pipe protocol quick reference ✅

- Pipe: `\\.\pipe\MSI_SERVICE_2`; service: `msiservice`
- Encryption: 3DES (key = MD5(handshake string))
- Commands: `HS` / `RMREQ` / `WMREQ` / `RPREQ` / `WPREQ` / `EVTWREQ` / Registry
- Responses: `HS:ACK/ERR`, `IO:RMRST/WMRST/RPRST/WPRST/ERR`, `REG:RRST/WRST/ERR`,
  `WMI:RRST/WRST/EVTWRST/ERR`

### 8.2 WMI classes quick reference ✅

`root\WMI`: `MSI_System` (System), `MSI_Power` (Power), `MSI_Device` (Device),
`MSI_Software` (Software), `MSI_CPU` (CPU), `MSI_VGA` (VGA), `MSI_AP` (AP),
`MSI_Master_Battery` (Master_Battery), `MSI_Event`.

### 8.3 Power-scheme GUIDs quick reference ✅

See the table in §4.3 (ten GUIDs).

### 8.4 Open items (require real-machine confirmation) 🔵

- [ ] EC fan-speed register offsets and RPM conversion on the target machine
- [ ] EC charge-threshold register offset and encoding
- [ ] Input parameter names and values for the `MSI_System` method
- [ ] Meaning of the `0/1/2` encoding in the `MSI_Master_Battery` property
- [ ] Whether CPU/GPU overclocking in Custom mode is supported on the target machine
  (`IntelOverclockingSDK` / NVAPI)

---

*These notes were produced by static analysis of the local `DC_BACKUP/` directory (.NET
metadata, strings, and IL disassembly, plus native DLL strings). Items marked ✅ were
directly confirmed in the binaries; 🟡 items are structural inferences; 🔵 items require
runtime probing. The GS65-specific runtime results are in
[02-ec-register-map.md](02-ec-register-map.md).*
