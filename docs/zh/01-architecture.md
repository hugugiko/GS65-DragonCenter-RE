# MSI Dragon Center (DC_BACKUP) 逆向解读 与 GHelper 类工具实现方案

**简体中文** | [English](../en/01-architecture.md)

> 目标：彻底搞清楚 MSI Dragon Center 官方控制程序的**通信工作逻辑**，用于开发一个类似 **GHelper**（华硕奥创替代品）的轻量开源替代工具。
>
> 分析对象：`DC_BACKUP/`（Dragon Center 2.x 安装目录的完整本地备份；本仓库不包含任何其中文件）
>
> 发布说明：本文为中文原文。为公开发布，已移除本地绝对路径，并在 §4.3 补充一处后续修正。
> 文中仅记录互操作性事实，不包含 MSI 的代码、二进制或转储内容；请先阅读 [NOTICE.md](../../NOTICE.md)。
>
> 结论等级标注：
> - ✅ **已从二进制验证**（字符串/元数据/IL 反汇编直接证实）
> - 🟡 **结构推断**（从类型/方法名与调用关系推断，未见明文常量）
> - 🔵 **模型相关，需运行时探测**（EC 寄存器偏移等随机型不同，需在真机 dump）

---

## 一、总体结论（TL;DR）

Dragon Center 不是"一个程序"，而是一套 **C/S 三层架构**：

```
┌─────────────────────────────────────────────────────────────────────┐
│  UI 层（用户态，普通权限）                                              │
│  Dragon Center.exe / CommandCenter_Start.exe / GameCenter-OC.exe      │
│  gpuControl.exe / AI Wizard.exe ...（全是 .NET WPF 程序）              │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ 命名管道 IPC（3DES 加密的 JSON）
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  服务层（用户态，SYSTEM 权限）                                         │
│  MSIAPService.exe（服务名 "msiservice"，常驻）                         │
│  —— 唯一的"硬件访问闸门"，UI 层不能直接碰硬件                           │
└───────┬──────────────────┬──────────────────────┬───────────────────┘
        │ WinIo 驱动        │ WMILib.dll (COM)      │ 注册表
        ▼                   ▼                       ▼
┌──────────────┐  ┌──────────────────────┐  ┌──────────────┐
│ EC 嵌入式控制器 │  │ ACPI WMI (root\WMI)   │  │ HKLM 等      │
│ 端口 0x62/0x66 │  │ MSI_System/Power/... │  │ 存配置/授权  │
│ (直接读写 RAM) │  │ MSI_Master_Battery   │  └──────────────┘
└──────────────┘  └──────────────────────┘
```

**三个核心事实（决定了整个方案怎么设计）：**

1. ✅ **UI 进程不直接访问硬件**。所有 EC/风扇/电池操作都先发到命名管道 `\\.\pipe\MSI_SERVICE_2`，由 `MSIAPService.exe` 转成对 EC/WMI/注册表的调用。**这意味着你可以完全绕开官方 UI，自己直接连这个管道（路径 A），或者干脆自己复刻服务层那三件事（路径 B）。**

2. ✅ **MSI 的"性能模式"本质是 Windows 电源计划（power plan）**。均衡/性能/影视/省电/自定义，对应一批预置的电源计划 GUID（见附录），通过 `powrprof.dll` 的 `PowerSetActiveScheme` 切换。这与华硕（ASUS 走 ACPI WMI/ATKACPI）不同。

3. ✅ **风扇 / 电池充电阈值 / EC 寄存器**走两条腿：**ACPI WMI**（`root\WMI` 下的 `MSI_System`、`MSI_Master_Battery` 等类）+ **EC RAM 直读直写**（WinIo 驱动 + 端口 0x62/0x66）。

---

## 二、DC_BACKUP 组件清单（谁是谁）

| 文件 | 类型 | 作用（逆向结论） |
|---|---|---|
| `Dragon Center.exe` | .NET WPF | **主 UI + 全部业务逻辑**。风扇曲线、电池、性能模式、WMI/EC 访问封装都在这里（IL 被混淆/加密保护） |
| `MSIAPP_Service/MSIAPService.exe` | .NET 服务 | **硬件访问服务**（未混淆，已完整反汇编）。命名管道服务器 + WinIo + WMI + 注册表桥 |
| `MSIAPP_Service/WMILib.dll` | 原生 C++ (COM) | WMI 的 COM 封装，导出 `ReadWMI / ReadWMIAll / WriteWMI` |
| `MSIAPP_Service/WinIo32/64.dll + .sys` | 原生驱动 | **WinIo 内核驱动**，提供 `GetPortVal/SetPortVal/GetPhysLong/SetPhysLong` 做端口/物理内存 I/O |
| `MSIECO.dll` | .NET | **"ECO 性能模式"模块**（未混淆，已完整反汇编）。把模式映射到 Windows 电源计划 |
| `MSIECO/*.eps` | 注册表蜂巢文件 | 电源计划导出文件（`regf` 格式），`PowerImportPowerScheme` 导入用 |
| `MsiHid.dll` | 原生 | HID 设备访问（Fn 键 / SteelSeries 键盘 / 特殊键） |
| `UEFIVaribleDll.dll` | 原生 | UEFI NVRAM 变量读写（改 BIOS 设置，如 Fn/Win 键互换） |
| `IntelOverclockingSDK.dll` | 原生 | Intel XTU SDK（**CPU 超频/降压** = "自定义模式"里的 CPU 调校） |
| `gpuControl.exe` | .NET | GPU 超频（NVAPI/`nvpowerapi.dll`，核心/显存时钟偏移） |
| `GameCenter-OC.exe` | .NET | 游戏中心 + CPU 核心超频入口（走 `IntelOverclockingSDK`） |
| `ProfileHelperModel.dll` | .NET | 用户"配置文件"（Profile）数据模型 |
| `AsyncSocketLib.dll` / `NamedPipeClientLib.dll` | .NET | 移动端互联 / 命名管道客户端（被官方 UI 使用） |
| `devcon.exe` | 原生 | 驱动安装/卸载工具（装 WinIo64.sys 用） |

> 🟡 你关心的三大功能（性能模式 / 风扇 / 电池）**都不需要** `IntelOverclockingSDK`、`gpuControl`、`MsiHid`——它们只与 EC、WMI、电源计划有关，这是实现轻量替代工具的好消息。

---

## 三、IPC 通信协议（UI ↔ 服务）✅ 已完整还原

### 3.1 命名管道

- 管道名：`\\.\pipe\MSI_SERVICE_2` ✅
- 服务名：`msiservice`（`MSIAPService.exe` 以 SYSTEM 权限常驻）✅
- 管道采用 `PIPE_TYPE_MESSAGE`（消息模式），安全描述符 `D:(A;OICI;GRGW;;;AU)(A;OICI;GA;;;BA)`（授权用户 + 管理员）✅

### 3.2 加密

数据不是明文，用的是 **3DES（TripleDES）+ MD5 派生密钥**：✅

- `System.Security.Cryptography.MD5CryptoServiceProvider` + `TripleDESCryptoServiceProvider`
- 密钥由**握手阶段**客户端发来的原始串经 MD5 派生（方法名 `GetClientRawStringForKeyGeneration`）
- 结论：**要复用官方服务，必须先握手拿到派生密钥**；这也是为什么自己复刻硬件访问（路径 B）更省事。

### 3.3 命令帧（客户端 → 服务，前缀 + JSON）

| 前缀 | 含义 | 说明 |
|---|---|---|
| `HS` | HandShake | 握手/密钥协商 |
| `RMREQ` | Read Memory Request | 读 EC RAM（物理内存/端口） |
| `WMREQ` | Write Memory Request | 写 EC RAM |
| `RPREQ` | Read Port Request | 读 I/O 端口 |
| `WPREQ` | Write Port Request | 写 I/O 端口 |
| `EVTWREQ` | Event Write Request | WMI 事件写入 |
| （注册表） | Read/Write Registry | JSON 带 `root/keyName/valueName/value` |

### 3.4 响应帧（服务 → 客户端）

| 前缀 | 含义 |
|---|---|
| `HS:ACK:` / `HS:ERR:` | 握手成功 / 失败 |
| `IO:RMRST:` / `IO:WMRST:` | 读/写内存响应 |
| `IO:RPRST:` / `IO:WPRST:` | 读/写端口响应 |
| `IO:ERR:` | IO 错误 |
| `REG:RRST:` / `REG:WRST:` / `REG:ERR:` | 注册表读/写/错误 |
| `WMI:RRST:` / `WMI:WRST:` / `WMI:EVTWRST:` / `WMI:ERR:` | WMI 读/写/事件/错误 |

JSON 键：`"WMIValue"`、`"RegistryValue"`；WMI 项为 `property/value`，注册表项为 `root/keyName/valueName/value`。✅

### 3.5 服务端硬件桥（`MSIAPService.WinIO` / `.WMI`）✅

服务里有两类 P/Invoke 封装：

- `WinIO` 类：字段 `EC_Ram_Address`、`EC_HIGH`、`EC_LOW`、`EC_DATA`；方法 `readECRam / ReadPort / WritePort / ReadMemory / WriteMemory / checkBackDoor`
- `WMI` 类：`readWMI / readWMIAll / writeWMI`（转发给 `WMILib.dll`）

> 🔵 `EC_HIGH/EC_LOW/EC_DATA` 的具体端口号在 `.cctor` 里以 `ldc.i4` 常量形式存在（IL 被混淆，未直接读到明文），但按 ACPI EC 标准惯例为 **0x66（命令/状态端口）、0x62（数据端口）**——这是 x86 笔记本 EC 的通用约定，所有开源 MSI EC 工具（MControlCenter、msi-ec）都用它。

---

## 四、硬件访问层详解

### 4.1 ACPI WMI 接口（MSI 的"万能总线"）✅ 已完整还原

这是**最关键、可直接复用**的发现。MSI 的固件暴露了一套 ACPI WMI 接口，命名空间 `root\WMI`：

| WMI 类 | 方法/属性 | 用途（逆向推断） |
|---|---|---|
| `MSI_System` | 方法 `System` | **系统状态：风扇转速、温度、模式标志** |
| `MSI_Power` | 属性 `Power` | **电源/性能模式（User Scenario）** |
| `MSI_Device` | 方法 `Device` | 设备开关（WiFi/蓝牙/摄像头等） |
| `MSI_Software` | 方法 `Software` | 软件类控制 |
| `MSI_CPU` | 属性 `CPU` | CPU 信息/温度 |
| `MSI_VGA` | 属性 `VGA` | GPU 信息/温度 |
| `MSI_AP` | 属性 `AP` | AP（Access Point）相关 |
| `MSI_Master_Battery` | 属性 `Master_Battery` | **电池管理大师（充电阈值）** |
| `MSI_Event` | — | **事件通知**（Fn 键切换模式、ECO 事件等） |

WQL 示例（直接取自二进制字符串）：✅
```
SELECT * FROM MSI_System
SELECT * FROM MSI_Device
SELECT Power FROM MSI_Power
SELECT CPU FROM MSI_CPU
SELECT VGA FROM MSI_VGA
SELECT Master_Battery FROM MSI_Master_Battery
SELECT * FROM MSI_Event
```

调用格式字符串（客户端自定义封装）：✅
```
读（Query）:  root\WMI:Q:MSI_System:System:
写（Set）  :  root\WMI:S:MSI_...
```

**这意味着你的替代工具可以用标准 `System.Management`（ManagementObject / InvokeMethod）直接读写这些 WMI 类，完全不需要官方服务。** 这是路径 B 的核心。

### 4.2 EC（嵌入式控制器）直接访问 🔵

- 通过 WinIo 驱动对端口 **0x66（命令）/ 0x62（数据）** 做 `GetPortVal/SetPortVal`，实现标准 ACPI EC 读/写。
- `readECRam` 即"写 EC 寄存器偏移 → 0x66，读写数据 → 0x62"。
- 客户端还封装了 `MSI_App_Service_ReadMemory / WriteMemory`（就是走管道 → 服务 → WinIo 的 `ReadMemory/WriteMemory`）。
- 示例：电池模式写入 `BatteryUI::WriteECtoBatteryMode` 的第一步是 `ReadMemory(0xFC0008EF)`（先读 EC 某寄存器再改位写回）🟡。

> 🔵 **EC 寄存器偏移（风扇转速地址、充电阈值地址、模式字节等）是机型相关的**，且藏在被混淆的 `Dragon Center.exe` IL 里。正确做法是运行时 EC dump（见 §7.3），这也是 GHelper/MControlCenter 的常规开发方式。

### 4.3 Windows 电源计划（性能模式的地基）✅ 已完整还原

`MSIECO.dll` 把"系统环境设置"里的每个档位映射到一个 **Windows 电源计划 GUID**：

| 档位 | 枚举 `EnumECOPS` | 电源计划 GUID | 来源 / 备注 |
|---|---|---|---|
| 均衡 Balance | `MSI_BALANCE` | `EC73D77B-025C-46F2-A867-46F201BE299F` | 自定义（MSI Balance.eps），静态解码 🟡 |
| 性能 Performance | `MSI_PERFORMANCE` | `2C6153B0-5B06-4FF1-9675-014B8E40E355` | 自定义（MSI Performance.eps），静态解码 🟡 |
| 游戏 Gaming | `ECO_GAMMING` | `98B32AC9-6345-4AB9-A981-0F0E39C08578` | Gaming.eps ✅ |
| 影视 Movie | `ECO_MOVIE` | `A469DC3C-170E-4428-989C-0133582FEC6F` | Movie.eps ✅（修正，见下） |
| 演示 Presentation | `ECO_PRESENTATION` | `C3407F92-A518-430B-94BF-9874575E931E` | Presentation.eps ✅ |
| 办公 Office | `ECO_OFFICE` | `DF8734A4-F9A5-49CF-A336-B8F6E6207807` | Office.eps ✅ |
| 省电 TurboBattery | `ECO_TURBOBATTERY` | `DB5648DC-C820-4FD8-B413-2CCCD48C273F` | TurboBattery.eps ✅ |
| Windows 均衡 | `BALANCED` | `381B4222-F694-41F0-9685-FF5BB260DF2E` | Windows 标准 |
| Windows 高性能 | `HIGH_PERFORMANCE` | `8C5E7FDA-E8BF-4A96-9A85-A6E23A8C635C` | Windows 标准 |
| Windows 节能 | `SAVING` | `A1841308-3541-4FAB-BC81-F71556F20B4A` | Windows 标准 |

> **修正（2026-10）**：早期从 `MSIECO.dll` IL 解出的影视模式 GUID（`0BC57CB5-…`）经后续核对为误读。
> 随软件发布的 `Movie.eps` hive 中实际写入的是 `A469DC3C-170E-4428-989C-0133582FEC6F`，应以落地文件为准
> （`.eps` 才是被真正导入的对象）。同一轮核对确认了上表中 Gaming / Presentation / Office / TurboBattery 的 GUID。

切换流程（`MSIECO.CECO` 的方法）：✅
```
SetECOPowerScheme(mode)
  → 首次运行时 PowerImportPowerScheme("xx.eps")  导入电源计划
  → PowerSetActiveScheme(GUID)                   切换活动计划
ActiveECOPowerScheme()  → PowerGetActiveScheme   读回当前计划
```

> 关键结论：**"性能/均衡/省电"三档 ≈ 切换电源计划**；"影视/游戏"等是 MSI 定制的电源计划。GHelper 对华硕多数模式走 ACPI，而 MSI 这一层其实是纯 Windows 机制，非常容易复刻（甚至可以直接 `powercfg /setactive <GUID>`）。

---

## 五、三大功能的逆向解读

### 5.1 系统环境设置（均衡 / 性能 / 影视 / 省电 + 自定义）✅🟡

- **四个预设档** = 调用 `MSIECO.dll` 切换电源计划（§4.3），同时通过 WMI `MSI_Power` / `MSI_System` 写一个"当前模式"标志到 EC，让键盘 Fn 切换、指示灯等感知。
- **"自定义模式"** = 一个用户 Profile（`ProfileHelperModel`），里面保存：
  - CPU 调校（`CPU_OverClock` → `IntelOverclockingSDK.dll`，含倍频 `CPU_Ratio_Index`、电压）🟡
  - GPU 调校（`gpuControl.exe` → NVAPI，`Core Clock Offset / VRAM Clock Offset`）🟡
  - 风扇曲线（见 5.2）
  - 屏幕/DPI、Nahimic 音效、LED 等杂项（不在本次范围）
- 相关枚举/类型：`.ECOModes`（ECO_GAMMING/MOVIE/PRESENTATION/OFFICE/TURBOBATTERY/ECO_DISABLE/BALANCED/HIGH_PERFORMANCE/SAVING）、`.ShiftType::ECO`、`Shift_Control`（"Shift"即 MSI 对性能模式的旧称）。

### 5.2 风扇转速：读取 + 控制 ✅🟡

`Dragon_Center.Controls.TuneMgr.SetFunction.FanSettings` 是整个风扇逻辑的核心：

- **转速读取**：WMI `MSI_System`（`SELECT * FROM MSI_System`）返回当前风扇 RPM；UI 里字段 `CpuFanSpeed / GpuFanSpeed / Fan3Speed / Fan4Speed`（最多 4 路风扇）。
- **手动控制 = 一条 6 点折线**（温度 → 风扇 %）：
  - CPU 风扇：`FanCPU1..6Temperature` + `Fan_CPU_Value_1..6`
  - GPU 风扇：`FanVGA1..6Temperature` + `Fan_VGA_Value_1..6`
- **风扇模式**：`Auto_Fan / Basic_Fan / Basic_CPU_Fan / Basic_VGA_Fan / Adv_Fan`，`Fan_Mode_Value`。
- **Cooler Boost（强冷）**：`IsCoolerBoost` 开关（风扇拉满）。
- **存储位置**：🟡 字段 `TableNotReload_ECRam` 表明风扇曲线表**存在 EC RAM 里**，通过 `MSI_App_Service_ReadMemory/WriteMemory` 读写（即 §4.2 的 EC 直读直写）。

> 🔵 风扇曲线的 EC 起始地址、每个点占几字节、RPM 的换算公式（通常是 `RPM = value * 100` 或查表）需在真机 dump 校准。

### 5.3 电池管理大师（充电电量状态）✅🟡

界面提供了**三种充电策略**（以下为行为概述，不是原文照录）：✅

| 选项 | 行为 |
|---|---|
| Best for Mobility（最佳移动性） | 始终保持充到 100% |
| Balanced（均衡） | 低于 70% 开始充电，充到 80% 停止 |
| Best for Battery（最佳电池寿命） | 低于 50% 开始充电，充到 60% 停止 |

实现路径（两条腿）：✅🟡
1. **WMI**：`SELECT Master_Battery FROM MSI_Master_Battery` 读当前充电状态/阈值，写同理（`SetWMIValue`）。
2. **EC**：`BatteryUI::WriteECtoBatteryMode` → `MSI_App_Service_ReadMemory/WriteMemory` 写 EC 的充电阈值寄存器（起始地址在 IL 里为 `0xFC0008EF` 一带，🟡 具体偏移需校准）。

> 补充：还有个独立的"**Quick Charge 3.0**"（USB 口快充开关，仅部分机型支持），与电池寿命管理是两回事，通过 `MSI_Device` 控制。

---

## 六、方案控制逻辑（如何造一个 GHelper 类工具）

### 6.1 两条实现路径对比

| | 路径 A：复用官方服务 | 路径 B：独立复刻（推荐） |
|---|---|---|
| 原理 | 连 `\\.\pipe\MSI_SERVICE_2`，用 3DES 加密 JSON 调 ReadMemory/WriteMemory/WMI | 自己加载驱动访问 EC + 自己调 WMI + 自己切电源计划 |
| 优点 | 不用碰驱动/EC 细节 | 完全独立、轻量、可开源、不依赖被放弃的官方组件 |
| 缺点 | 依赖官方 `msiservice`（已停更）；要破解 3DES 握手密钥 | 需要管理员权限加载驱动；EC 偏移要逐机 dump |
| 与 GHelper 类比 | 不推荐 | **这就是 GHelper 的做法**（GHelper 也不依赖 ASUS 的 Armoury Crate） |

**推荐路径 B**，理由：官方服务停更、且其协议带私有加密握手；而 MSI 的底层其实是**标准 ACPI EC + 标准 WMI + 标准 Windows 电源计划**，三者都有公开可复刻的方式。

### 6.2 目标工具的分层设计（路径 B）

```
┌─────────────────────────────────────────────┐
│  UI 层（WPF / WinUI / Electron 任选）          │
│  - 模式切换按钮（均衡/性能/影视/省电/自定义）      │
│  - 风扇曲线编辑器 + Cooler Boost               │
│  - 电池阈值三档选择                             │
│  - 转速/温度/功耗 实时监视                       │
└──────────────────────┬──────────────────────┘
                       │
┌──────────────────────▼──────────────────────┐
│  控制核心（C#/.NET 最省事，System.Management 现成）│
│  ┌─────────────┐ ┌──────────┐ ┌─────────────┐ │
│  │ EC 驱动访问  │ │ WMI 访问  │ │ 电源计划     │ │
│  │ (WinIo/inpout│ │ root\WMI │ │ powercfg/   │ │
│  │  0x62/0x66) │ │ MSI_*    │ │ PowerSetAct │ │
│  └─────────────┘ └──────────┘ └─────────────┘ │
└───────────────────────────────────────────────┘
```

### 6.3 每个功能的落地动作

| 功能 | 读（监视） | 写（控制） |
|---|---|---|
| 性能模式 | `PowerGetActiveScheme` / WMI `MSI_Power` | `PowerSetActiveScheme(GUID)` + 写 WMI `MSI_Power`/`MSI_System` 模式字节 |
| 风扇转速 | WMI `SELECT * FROM MSI_System`（RPM）；或 EC 读转速寄存器 | 写 EC 风扇曲线表 + 风扇模式字节；`IsCoolerBoost` |
| 电池阈值 | WMI `SELECT Master_Battery FROM MSI_Master_Battery` | 写 WMI `MSI_Master_Battery` + 写 EC 充电阈值寄存器 |

### 6.4 关键难点与规避策略

1. **EC 寄存器偏移未知（模型相关）** → 用**运行时 EC dump**：写一个 dump 工具，遍历 EC 0x00–0xFF，记录"改风扇/改模式/改电池"前后变化的字节，反推偏移。开源参考：`MControlCenter`（MCC）、Linux 的 `msi-ec` 内核模块已经整理了大量 MSI 机型的 EC 布局，可直接对照。
2. **驱动权限** → 复用 `WinIo64.sys`（DC_BACKUP 里就有）或 `inpout32`，仅需安装一次；也可用 `RWEverything`/`WinRing0`。
3. **WMI 方法参数名** → 用 `PowerShell` 的 `Get-WmiObject -Namespace root\WMI -Class MSI_System` 直接枚举属性/方法（比反汇编更快更准），见 §7.2。

---

## 七、给逆向/复刻者的实操手册

### 7.1 快速验证 WMI（30 秒确认硬件接口可用）

```powershell
# 枚举 MSI ACPI WMI 类
Get-WmiObject -Namespace root\WMI -List | Where-Object { $_.Name -like 'MSI_*' }

# 读系统/风扇相关
Get-WmiObject -Namespace root\WMI -Class MSI_System | Format-List *
Get-WmiObject -Namespace root\WMI -Query "SELECT * FROM MSI_System"

# 读电池
Get-WmiObject -Namespace root\WMI -Query "SELECT Master_Battery FROM MSI_Master_Battery"

# 读电源模式
Get-WmiObject -Namespace root\WMI -Query "SELECT Power FROM MSI_Power"
```

### 7.2 用 PowerShell 反推 WMI 方法签名

```powershell
$c = Get-WmiObject -Namespace root\WMI -Class MSI_System
$c.GetType().GetMethods()          # 列出方法
$c | Get-Member                    # 列出属性
# 若要调方法：Invoke-WmiMethod -Namespace root\WMI -Class MSI_System -Name System -ArgumentList ...
```

### 7.3 用 EC dump 反推寄存器偏移（风扇/电池的核心）

1. 以管理员加载 `WinIo64.sys`，写最小 EC 读写器（`out 0x66, idx; in 0x62`）。
2. 全量 dump EC 0x00–0xFF 到一个文件。
3. 在官方 Dragon Center 里改一个状态（例如：风扇从 30%→100%，或电池从"100%"→"80%"），再次 dump。
4. `diff` 两次 dump，变化的字节就是目标寄存器。多试几次确认。
5. 用得到的偏移写进你的工具，做机型白名单（像 GHelper 的机型配置一样）。

### 7.4 复刻官方服务的等价调用

| 官方内部调用 | 你的等价实现 |
|---|---|
| `WinIO.GetPortVal/SetPortVal` | 自加载 WinIo64.sys 后 `GetPortVal/SetPortVal` |
| `WinIO.readECRam` | 标准 EC：`out 0x66, addr; ... ; in 0x62` |
| `WMILib.ReadWMI/WriteWMI` | `System.Management` 的 `ManagementObject` |
| `MSIECO.SetECOPowerScheme` | `powercfg /setactive <GUID>` 或 P/Invoke `PowerSetActiveScheme` |

---

## 八、附录

### 8.1 命名管道协议速查 ✅

- 管道：`\\.\pipe\MSI_SERVICE_2`；服务：`msiservice`
- 加密：3DES（密钥=MD5(握手串)）
- 命令：`HS` / `RMREQ` / `WMREQ` / `RPREQ` / `WPREQ` / `EVTWREQ` / Registry
- 响应：`HS:ACK/ERR`、`IO:RMRST/WMRST/RPRST/WPRST/ERR`、`REG:RRST/WRST/ERR`、`WMI:RRST/WRST/EVTWRST/ERR`

### 8.2 WMI 类速查 ✅

`root\WMI`：`MSI_System`(System)、`MSI_Power`(Power)、`MSI_Device`(Device)、`MSI_Software`(Software)、`MSI_CPU`(CPU)、`MSI_VGA`(VGA)、`MSI_AP`(AP)、`MSI_Master_Battery`(Master_Battery)、`MSI_Event`

### 8.3 电源计划 GUID 速查 ✅

见 §4.3 表格（10 个 GUID）。

### 8.4 待办（需要真机确认的清单）🔵

- [ ] 本机 EC 风扇转速寄存器偏移 + RPM 换算
- [ ] 本机 EC 充电阈值寄存器偏移 + 编码
- [ ] 本机 `MSI_System` 方法的输入参数名/取值
- [ ] 本机 `MSI_Master_Battery` 属性值的 0/1/2 编码含义
- [ ] 自定义模式的 CPU/GPU 超频是否在本机支持（IntelOverclockingSDK / NVAPI）

---

*本报告由对 DC_BACKUP 目录的静态逆向（.NET 元数据/字符串/IL 反汇编 + 原生 DLL 字符串）生成；标注 ✅ 的为二进制中直接验证的结论，🟡 为结构推断，🔵 需在真机运行时探测确认。*
