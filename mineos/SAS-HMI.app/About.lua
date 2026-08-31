-- MineOS application metadata. MineOS resolves a runnable GUI application
-- from a "<Name>.app" directory containing this file plus Main.lua; the
-- exact field names/shape below are the best-effort convention documented
-- for MineOS applications and should be confirmed/adjusted against the
-- real MineOS source before first deployment (see the MineOS risk note in
-- README.md -- this is the one place in the whole SAS system where we are
-- targeting an API we could not directly inspect).
return {
  name = "SAS HMI",
  description = "IEC 61850-style substation automation HMI: mimic diagram, control, alarms and history, talking to an OC-IEC61850-SAS SCADA node.",
  developer = "rsmith01008",
  version = "1.0.0",
  icon = "Resources/icon.pic",
}
