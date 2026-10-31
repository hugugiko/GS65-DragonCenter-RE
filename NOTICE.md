# Legal and Copyright Notice

This repository is an **independent, unofficial research project**. It is not affiliated
with, sponsored by, or endorsed by Micro-Star International Co., Ltd. ("MSI").

## 1. No proprietary material is redistributed

This repository does **not** contain, and contributions must not contain:

- MSI executables, DLLs, drivers (`.sys`), installers, or firmware;
- MSI power-scheme files (`.eps`) or registry hives derived from them;
- extracted strings, metadata dumps, IL disassembly, decompiled source, or other
  reproductions of MSI software;
- screenshots, icons, or artwork from MSI software;
- license keys, serial numbers, or activation data.

The documents summarize **functional facts** required for interoperability — interface
names, register offsets, identifiers, and protocol framing — that were independently
derived from a locally owned installation. Facts and functional interface information
are generally not protected as the expression of a computer program, but the legal
treatment of reverse engineering still depends on your jurisdiction and on the
software's EULA.

## 2. Trademarks

"MSI", "Dragon Center", "Cooler Boost", "True Color", and related names and logos are
trademarks or registered trademarks of Micro-Star International Co., Ltd. They are used
here **nominatively**, solely to identify the software and hardware under study. No
trademark license is granted, and no endorsement is implied.

## 3. Reverse engineering and your EULA

Many software licenses prohibit reverse engineering, and some jurisdictions restrict it
independently of contract. Certain jurisdictions provide limited exceptions for
interoperability — for example, Article 6 of the EU Software Directive
(2009/24/EC) on decompilation for interoperability, or the interoperability exception in
17 U.S.C. § 1201(f) for circumvention. This project makes no representation that your
use is permitted.

**If you are bound by an EULA that prohibits reverse engineering, do not use this
material.** You are solely responsible for determining whether your use is lawful.

Nothing in this repository is legal advice.

## 4. Hardware risk

Direct EC writes can change fan behavior, charging behavior, thermal limits, or other
firmware-managed state. Incorrect writes may cause instability, data loss, or hardware
damage, and may void your warranty. All register values here are **observations from one
machine model and firmware revision**, not a specification. Use them at your own risk.
The authors provide no warranty of any kind.

## 5. No warranty

The material is provided "as is", without warranty of any kind, express or implied,
including but not limited to the warranties of merchantability, fitness for a particular
purpose, and non-infringement. See [LICENSE](LICENSE) and [LICENSE-docs](LICENSE-docs).

## 6. Third-party tools

The scripts under `tools/` depend on third-party Python packages:

- `dnfile` — MIT License
- `dncil` — MIT License
- `pefile` — MIT License

They are not vendored here. Their licenses apply to their respective code.

## 7. AI assistance

The writing, translation, and editing of the reverse-engineering documentation in this
repository was carried out with the participation of **DeepSeek v4 Flash** and
**DeepSeek v4 Pro**. The human author directed the analysis, performed and verified the
technical work against the binary and runtime evidence, and remains responsible for the
published content. This disclosure does not imply any endorsement by DeepSeek.

## 8. Takedown and contact

If you are a rights holder and believe this repository contains material that infringes
your rights, please open an issue or contact the repository owner through GitHub. We will
review and remove any material that should not be published.

---

*Last updated: 2026-10-31*
