-- sas.protection.curves: standard IEC 60255-151 / IEEE C37.112
-- inverse-time overcurrent trip-time formulas.
--
-- Pure math, deliberately zero OC-API coupling (no `component`, no
-- `event`, no globals beyond standard Lua) -- unlike almost everything
-- else in this codebase, this module can be exercised with a plain
-- `lua5.3` run outside the game (see tests/protection/test_curves.lua),
-- not just syntax-checked with `luac5.3 -p`. Keep it that way: any
-- OC-specific concern (reading a meter, applying a trip) belongs in
-- sas/protection/ptoc.lua's tick integration, not here.
local curves = {}

-- Each formula computes time-to-trip in seconds at a constant multiple
-- of pickup, given M = measured/pickup (already validated > 1 by the
-- caller) and tms (the time-multiplier/dial setting). Formulas and
-- coefficients per IEC 60255-151:2009 Table 1 and IEEE C37.112-1996
-- Table 1.
local FORMULAS = {
  IEC_STANDARD_INVERSE  = function(M, tms) return tms * (0.14 / (M ^ 0.02 - 1)) end,
  IEC_VERY_INVERSE      = function(M, tms) return tms * (13.5 / (M - 1)) end,
  IEC_EXTREMELY_INVERSE = function(M, tms) return tms * (80 / (M ^ 2 - 1)) end,
  IEEE_MOD_INVERSE      = function(M, tms) return tms * (0.0515 / (M ^ 0.02 - 1) + 0.1140) end,
  IEEE_VERY_INVERSE     = function(M, tms) return tms * (19.61 / (M ^ 2 - 1) + 0.491) end,
  IEEE_EXTREME_INVERSE  = function(M, tms) return tms * (28.2 / (M ^ 2 - 1) + 0.1217) end,
}

-- Sorted list of recognized curve names, for config validation error
-- messages and the SCL compiler's own validation (kept alongside the
-- formula table it's derived from rather than hand-duplicated).
curves.NAMES = {}
for name in pairs(FORMULAS) do table.insert(curves.NAMES, name) end
table.sort(curves.NAMES)

function curves.isKnown(name)
  return FORMULAS[name] ~= nil
end

-- Returns time-to-trip in seconds for `name` at M=measured/pickup with
-- time-multiplier `tms`, or nil, err if `name` is unrecognized or M<=1
-- (no trip condition -- not an error, just "never trips at this M").
-- DEFINITE_TIME is intentionally NOT handled here: it has no formula (a
-- fixed delay isn't a function of M), so sas/protection/ptoc.lua handles
-- that curve name itself before ever calling into this module.
function curves.timeToTrip(name, M, tms)
  local f = FORMULAS[name]
  if not f then return nil, "unknown curve: " .. tostring(name) end
  if M == nil or M <= 1 then return nil end
  return f(M, tms)
end

return curves
