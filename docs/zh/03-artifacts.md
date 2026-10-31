# 逆向产物说明

[English](../en/03-artifacts.md) | **简体中文**

本页说明研究 Dragon Center 过程中在本地生成的中间产物，并解释为什么这些原始产物
**有意不收录**在本仓库中。

---

## 1. 产物是什么

分析过程中生成了三类中间文件，全部由合法获得的软件副本在本地生成：

| 产物 | 生成工具 | 内容 |
|---|---|---|
| `*.txt`（如 `MSIAPService.exe.txt`） | `tools/dump_dotnet.py` | .NET 元数据：类型定义、字段与常量、方法定义、P/Invoke 导入、类型引用、用户字符串 |
| `*.str.txt`（如 `Dragon Center.exe.str.txt`） | `tools/strings_extract.py` | 从 PE 二进制中提取的 ASCII 与 UTF-16LE 字符串 |
| `*_il.txt`（如 `fan_il.txt`、`batt_il.txt`） | `tools/il_dump.py` | 对方法全名匹配指定子串的方法进行 IL 反汇编 |

具体研究过的文件：

| 文件 | 关注的程序集 / 方法 |
|---|---|
| `MSIAPService.exe.txt` / `.str.txt` | 服务端类型：`WinIO`、`WMI`、`NativeNamedPipeServer`、`EncrptyDecrypt`；管道名、命令前缀、JSON 键、加密线索 |
| `MSIECO.dll.txt` / `eco_il.txt` | ECO 模式枚举与电源方案切换方法 |
| `Dragon Center.exe.txt` / `.str.txt` | 客户端类型 `FanSettings`、`BatteryUI`、`SCM`、`WinAndFnChange` 等；WMI 类与 WQL 查询 |
| `WMILib.dll.str.txt` | 原生 WMI COM 封装导出 `ReadWMI`、`ReadWMIAll`、`WriteWMI` |
| `MsiHid.dll.str.txt`、`UEFIVaribleDll.dll.str.txt` | HID 与 UEFI 变量访问（风扇/电池/模式不需要） |
| `ProfileHelperModel.dll.txt` / `.str.txt` | 用户 Profile 数据模型 |
| `WinIo64.dll.str.txt` | WinIo 驱动导出与端口 I/O 入口 |
| 其他 `.exe.txt` / `.str.txt` | `CommandCenter_Start`、`GameCenter-OC`、`gpuControl`、`MSIAPService` |
| `fan_il.txt`、`batt_il.txt`、`wafc_il.txt`、`scm_il.txt`、`winio_il.txt`、`enc_il.txt` | 针对风扇、电池、WMI/ACPI、系统控制、WinIo、加密方法的定向 IL 反汇编 |

---

## 2. 为什么不公开原始产物

这些文件是**对专有程序的派生复制**：元数据转储复制了程序的类型与方法结构，字符串转储复制了
其内嵌字符串资源，IL 转储复制了其可执行逻辑。公开它们等于再分发 MSI 版权作品的实质性部分，
也可能与软件 EULA 冲突。

对本仓库的目的而言，它们也不是必需的。互操作性真正需要的是从中提炼出的少量功能性事实，
这些事实已记录在：

- [01-architecture.md](01-architecture.md) —— 架构、协议、WMI 类、电源方案 GUID；
- [02-ec-register-map.md](02-ec-register-map.md) —— 校准得到的 EC 偏移。

[`tools/`](../../tools/) 下的辅助**脚本**是原创作品，以 MIT 许可证发布，不包含任何 MSI 数据。

---

## 3. 复现这些产物

如果你拥有该软件的副本，可以为自己的研究重新生成这些产物：

```bash
pip install dnfile dncil pefile

python tools/dump_dotnet.py "path/to/Assembly.exe"
python tools/strings_extract.py "path/to/Assembly.exe"
python tools/il_dump.py "path/to/Assembly.exe" "FanSettings" fan_il.txt
```

前两个脚本把输出写到当前目录，`il_dump.py` 写到指定路径。请把这些输出视为专有材料：

- 不要提交到本仓库或任何公开仓库；
- 不要在 issue 或 pull request 中粘贴大段摘录；
- 只像本仓库这样总结功能性事实。

`.gitignore` 已排除可执行文件、驱动、`.eps` hive、`.bin` 转储以及 `*.str.txt` / IL 输出，
以降低误发布的风险。

---

## 4. 公开内容的范围

| 项目 | 是否公开 | 原因 |
|---|---|---|
| 架构描述 | ✅ 是 | 功能性事实，独立撰写 |
| 命名管道分帧与前缀 | ✅ 是 | 互操作性事实 |
| WMI 类名与 WQL 形式 | ✅ 是 | 互操作性事实 |
| 电源方案 GUID | ✅ 是 | 标识符事实 |
| 某一机型的 EC 寄存器偏移 | ✅ 是 | 运行时观测结果 |
| 原始元数据 / 字符串 / IL 转储 | ❌ 否 | 对专有代码的派生复制 |
| MSI 二进制、驱动、`.eps` 文件 | ❌ 否 | 直接再分发专有文件 |
| 私有探测/控制工具源码 | ❌ 否 | 不属于本次公开内容 |

---

*完整法律声明见 [NOTICE.md](../../NOTICE.md)。*
