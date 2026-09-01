# Vendored SCL2007B4 schema

These `.xsd` files are vendored unmodified from
[com-pas/compas-scl-xsd](https://github.com/com-pas/compas-scl-xsd),
`src/main/resources/xsd/SCL2007B4/`, commit `f41cc23ed058e4a89c752488c705ac5a8d8918af`
(2025-03-13). That repo is Apache-2.0 licensed (see its `LICENSES/Apache-2.0.txt`).

The schema content itself (`SCL2007B4` = IEC 61850-6 Ed 2.1, i.e.
IEC 61850-6:2009/AMD1:2018) carries IEC's own copyright notice embedded
in each file's header:

> COPYRIGHT (c) IEC, 2018. This version of this XSD is part of
> IEC 61850-6:2009/AMD1:2018; see the IEC 61850-6:2009/AMD1:2018 for full
> legal notices.

`SCL.xsd` is the entry point; it includes `SCL_Substation.xsd`,
`SCL_Communication.xsd`, `SCL_IED.xsd`, `SCL_DataTypeTemplates.xsd`,
`SCL_Enums.xsd`, `SCL_BaseTypes.xsd`, `SCL_BaseSimpleTypes.xsd`, and (for
the `Header`/history elements) `IECCopyright.xsd`/`IECManifest.xsd`.

Used by `tools/scl-compiler/scl/validate.py` to XSD-validate
`scl/switchyard.scd` before compiling it (`--validate-xsd` flag on
`scl_compile.py`), and referenced throughout `tools/scl-compiler/scl/`'s
docstrings for the exact element/attribute names being mapped.

To update: replace these files with a newer commit's
`src/main/resources/xsd/SCL2007B4/*.xsd` from the same upstream repo, and
update the commit hash above.
