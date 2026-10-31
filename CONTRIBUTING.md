# Contributing

Contributions that improve the accuracy, clarity, or reproducibility of these notes are
welcome. Because this repository documents proprietary software, there are strict rules
about what may be submitted.

## Do not submit

- MSI binaries, DLLs, drivers, installers, firmware, or `.eps` files;
- decompiled source, IL dumps, metadata dumps, or extracted string tables;
- screenshots or assets from MSI software;
- anything obtained from a source other than a legally owned copy;
- instructions for bypassing licensing, activation, or security controls.

Pull requests containing such material will be closed and the content removed.

## Do submit

- corrections to documented facts, with the evidence level stated
  (verified / inferred / model-specific);
- results from **your own** hardware, clearly labelled with model, EC firmware, and BIOS
  version;
- improvements to the helper scripts that do not embed proprietary data;
- documentation fixes and translations.

## Evidence labels

Please keep the convention used in the documents:

| Label | Meaning |
|---|---|
| ✅ Verified | Confirmed directly from a binary, a documented API, or repeated runtime measurement |
| 🟡 Inferred | Derived from naming, call relationships, or a single observation |
| 🔵 Model-specific | Requires runtime calibration and may differ on other hardware |

## Licensing of contributions

By submitting a contribution you agree that:

- code contributions are licensed under the MIT License (see [LICENSE](LICENSE));
- documentation contributions are licensed under CC BY 4.0 (see [LICENSE-docs](LICENSE-docs)).

Do not submit material you do not have the right to license.
