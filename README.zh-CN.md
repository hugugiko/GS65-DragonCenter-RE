# MSI Dragon Center 逆向分析笔记

[English](README.md) | **简体中文**

本仓库是对 **MSI Dragon Center 2.x** 通信架构的**非官方独立逆向分析笔记**，起因是评估能否在
2019 款 MSI GS65 Stealth 9SE 上用一款轻量的开源控制工具（类似 GHelper 的思路）替代官方软件。

> 本仓库**不包含任何 MSI 二进制文件、驱动、安装包、电源方案文件，也不包含反编译得到的代码或字符串**。
> 这里只记录独立分析得出的、与互操作性有关的功能性事实（WMI 类名、EC 寄存器偏移、电源方案 GUID、
> 协议分帧方式）。使用或再分发前请阅读 [NOTICE.md](NOTICE.md)。

---

## 内容导航

| 文档 | 语言 | 内容 |
|---|---|---|
| [架构分析](docs/zh/01-architecture.md) | 中文 | 三层架构、命名管道协议、WMI/EC/电源计划访问、功能逆向、实现方案 |
| [EC 寄存器表](docs/zh/02-ec-register-map.md) | 中文 | 在 GS65 Stealth 9SE（MS-16Q4）上校准的机型相关偏移 |
| [逆向产物说明](docs/zh/03-artifacts.md) | 中文 | 本地转储产物是什么、如何生成、为何不公开 |
| [Architecture notes](docs/en/01-architecture.md) | EN | 架构分析的英文版 |
| [EC register map](docs/en/02-ec-register-map.md) | EN | 寄存器表的英文版 |
| [Artifact inventory](docs/en/03-artifacts.md) | EN | 逆向产物说明的英文版 |
| [tools/](tools/) | EN | 自行编写的 .NET 元数据 / 字符串 / IL 提取脚本 |

用于校准 EC 的**探测与控制程序（probe）不在本仓库中分享**。文档只记录这些程序得出的结论，
这样在不分发工具本身的情况下，笔记仍然可用。

---

## 主要结论

1. **Dragon Center 是一套三层架构。** WPF 界面进程从不直接访问硬件；它通过命名管道
   `\\.\pipe\MSI_SERVICE_2` 向 SYSTEM 服务 `MSIAPService.exe`（服务名 `msiservice`）发送
   加密 JSON，由服务层统一访问 EC、ACPI WMI 与注册表。
2. **性能模式本质上是 Windows 电源计划。** "系统环境设置"的各个预设对应电源方案 GUID；
   `MSIECO.dll` 负责导入 `.eps` hive 并通过 `powrprof.dll` 切换活动方案。这一层完全是
   Windows 机制，很容易复刻。
3. **风扇与电池控制走两条通路：** `root\WMI` 下的 ACPI WMI 类（`MSI_System`、`MSI_Power`、
   `MSI_Master_Battery` 等），以及通过 WinIo 驱动对 EC 端口 `0x62`/`0x66` 的直接读写。
4. **EC 偏移与机型相关。** 在 GS65 9SE（MS-16Q4）上，温度、风扇档位、风扇模式、强冷、
   电池阈值和手动风扇曲线的可用偏移，是通过 EC 差异转储校准得到的。见[寄存器表](docs/zh/02-ec-register-map.md)。
5. **独立复刻比复用已停更的官方服务更可行也更干净：** MSI 的底层就是标准 ACPI EC、
   标准 WMI 和标准 Windows 电源计划。

---

## 仓库结构

```
RE_repository/
├── README.md                  # 英文说明
├── README.zh-CN.md            # 本文件
├── NOTICE.md                  # 法律 / 版权 / 商标声明
├── CONTRIBUTING.md            # 贡献规则（禁止提交专有产物）
├── LICENSE                    # MIT —— 原创代码与工具
├── LICENSE-docs               # CC BY 4.0 —— 原创文档
├── docs/
│   ├── en/                    # 英文文档
│   └── zh/                    # 中文文档（原文 / 译文）
└── tools/                     # 自行编写的 .NET 元数据 / 字符串 / IL 转储脚本
```

---

## 复现分析

需要你**自己合法获得**的软件副本，以及 Python 3.9+。

```bash
pip install dnfile dncil pefile

# 转储 .NET 元数据（类型、字段、方法、P/Invoke、枚举）
python tools/dump_dotnet.py "path/to/YourAssembly.exe"

# 提取 ASCII + UTF-16LE 字符串
python tools/strings_extract.py "path/to/YourAssembly.exe"

# 反汇编名称包含指定子串的方法 IL
python tools/il_dump.py "path/to/YourAssembly.exe" "FanSettings" fan_il.txt
```

前两个脚本把输出写到当前目录，`il_dump.py` 写到指定路径。**请勿公开这些输出**——它们会复制
专有二进制中的元数据和代码。

EC 校准的标准差异转储方法见[架构分析 §7.3](docs/zh/01-architecture.md#73-用-ec-dump-反推寄存器偏移风扇电池的核心)。
只需要一个通用的 EC 转储与寄存器 diff 流程，以及你自行选择加载的驱动。

---

## 先行工作

MSI 的 EC 布局已被多个开源项目研究过（例如 `msi-ec`、`MControlCenter`、`isw`）。它们公开的
寄存器表可用于交叉验证。本仓库中 GS65 的具体数值是独立校准得到的**观测结果**，而非官方规范。

---

## 作者与 AI 参与声明

本仓库逆向内容的**撰写、翻译与编辑**由 **DeepSeek v4 Flash** 与 **DeepSeek v4 Pro**
参与完成。人类作者（hugugiko）负责设计分析方案、执行并核验基于二进制与运行时证据的技术工作，
并对公开内容负责。本声明不表示 DeepSeek 对本项目存在背书关系。

---

## 法律声明

本项目是**非官方研究**，与微星科技（Micro-Star International，MSI）无隶属或背书关系。
"MSI"、"Dragon Center" 及相关标识归其各自权利人所有，此处仅用于指代所研究的软件。
本仓库不重分发任何 MSI 代码或二进制文件。逆向工程可能受软件 EULA 和当地法律限制；
使用或贡献本仓库内容前，请自行评估相关风险。**请阅读 [NOTICE.md](NOTICE.md)。**

本文不构成法律意见。

---

## 许可证

- 原创**代码与脚本**：[MIT](LICENSE)
- 原创**文档**：[CC BY 4.0](LICENSE-docs)

Copyright (c) 2026 hugugiko。
