# 分析辅助脚本

[English](README.md) | **简体中文**

静态分析期间使用的原创极简 Python 辅助脚本。它们不包含任何 MSI 数据，按
[MIT 许可证](../LICENSE)发布。

> 这些脚本会从 .NET 程序集中提取元数据、字符串和 IL。**输出内容是对专有软件的复制**——
> 仅限个人研究使用，请勿提交或公开。见 [NOTICE.md](../NOTICE.md)。

## 依赖

- Python 3.9+
- `pip install dnfile dncil pefile`

## `dump_dotnet.py`

转储 .NET 元数据：类型定义、字段（含常量）、方法定义、P/Invoke 导入、类型引用和用户字符串。
对非托管输入会报告 `NOT MANAGED`。

```bash
python dump_dotnet.py Assembly.exe [MoreAssemblies.exe ...]
```

输出：当前工作目录下的 `<程序集文件名>.txt`。

## `strings_extract.py`

提取可打印 ASCII 与 UTF-16LE 字符串（最小长度 5），并去重。

```bash
python strings_extract.py Assembly.exe [MoreFiles ...]
```

输出：当前工作目录下的 `<文件名>.str.txt`。

## `il_dump.py`

对全名（`Namespace.Type::Method`）包含指定子串（不区分大小写）的方法进行 IL 反汇编，
并尽可能解析字符串、方法、字段和类型 token。

```bash
python il_dump.py Assembly.exe FanSettings fan_il.txt
```

参数依次为：输入程序集、名称过滤子串、输出文件。

## 说明

- `dump_dotnet.py` 与 `strings_extract.py` 把输出写到**当前目录**，而不是输入文件旁边；
  请在一个临时目录中运行。
- `il_dump.py` 从方法 RVA 起最多读取 0x20000 字节；超大方法可能被截断并标记
  `<FAILED …>`。
- 这些是研究用工具，不是生产级软件，可能存在粗糙之处。
