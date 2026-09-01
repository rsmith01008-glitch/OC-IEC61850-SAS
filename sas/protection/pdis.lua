-- sas.protection.pdis: distance protection (IEC 61850 PDIS) -- NOT
-- FUNCTIONAL. Modeled for SCL/data-model completeness only (zone-reach
-- settings are declared and carried through config so the point exists
-- and is addressable), but no trip logic is evaluated.
--
-- Why: distance protection computes impedance as a ratio of complex
-- voltage and current PHASORS (magnitude + angle). Create: Electro-
-- Energistics' gauge blocks expose only a scalar magnitude via
-- getValue() (see sas/io/meter.lua's header) -- there is no phase-angle
-- data source available on this hardware. A magnitude-only "impedance"
-- (V/I as plain numbers, discarding angle) is not distance protection;
-- it would misoperate for any fault with non-trivial angle, which is
-- most of them. Rather than ship a scheme that LOOKS like it's doing
-- distance protection but silently isn't, this module deliberately does
-- nothing at runtime beyond announcing that fact once at startup and
-- keeping the configured point addressable on SCADA/HMI screens.
--
-- If a real phase-angle data source ever becomes available in-game, real
-- distance-zone trip logic would belong here, following the same
-- validate()/newState()/tick() shape as sas/protection/ptoc.lua.
local pdis = {}

-- Validates one pdis scheme config -- structural only (this never
-- evaluates a trip, so there's nothing to check beyond "well-formed
-- enough to log and register the Op point").
function pdis.validate(cfg)
  if type(cfg.name) ~= "string" or cfg.name == "" then
    return nil, "protection.pdis: missing name"
  end
  return true
end

-- Logs once at IED startup so this is impossible to miss in `iedd`'s log
-- (and via `sas-ctl log`) -- see README.md's Protection section for the
-- full explanation this message points to.
function pdis.logInert(log, cfg)
  log("warn", "protection: PDIS '%s' loaded but NOT FUNCTIONAL -- distance protection needs V/I phasors "
    .. "(magnitude+angle); Create:EE meters only expose scalar magnitude. See README.md Protection section.",
    cfg.name)
end

return pdis
