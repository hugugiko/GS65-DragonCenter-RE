# Analysis Helper Scripts

**English** | [简体中文](README.zh-CN.md)

Original, minimal Python helpers used during the static analysis. They contain no MSI
data and are licensed under the [MIT License](../LICENSE).

> These scripts extract metadata, strings, and IL from a .NET assembly. **The output is
> a reproduction of proprietary software** — use it for your own research only, and do
> not commit or publish it. See [NOTICE.md](../NOTICE.md).

## Requirements

- Python 3.9+
- `pip install dnfile dncil pefile`

## `dump_dotnet.py`

Dumps .NET metadata: type definitions, fields (with constants), method definitions,
P/Invoke imports, type references, and user strings. Works on non-managed inputs by
reporting `NOT MANAGED`.

```bash
python dump_dotnet.py Assembly.exe [MoreAssemblies.exe ...]
```

Output: `<assembly-basename>.txt` in the current working directory.

## `strings_extract.py`

Extracts printable ASCII and UTF-16LE strings (minimum length 5), de-duplicated.

```bash
python strings_extract.py Assembly.exe [MoreFiles ...]
```

Output: `<file-basename>.str.txt` in the current working directory.

## `il_dump.py`

Disassembles the IL of every method whose full name (`Namespace.Type::Method`) contains
the given case-insensitive substring. Resolves string, method, field, and type tokens
where possible.

```bash
python il_dump.py Assembly.exe FanSettings fan_il.txt
```

Arguments: input assembly, name filter, output file.

## Notes

- `dump_dotnet.py` and `strings_extract.py` write output to the **current directory**,
  not beside the input. Run them in a scratch directory.
- `il_dump.py` reads up to 0x20000 bytes from the method RVA; very large methods may be
  truncated with a `<FAILED …>` marker.
- These are research utilities, not production tools. Expect rough edges.
