-- sas.protection.pdif: transformer differential protection (IEC 61850
-- PDIF), a deliberately simplified magnitude-restrained scheme --
-- current magnitude only, no vector/phase-shift compensation across
-- winding groups (the same magnitude-only hardware limitation as
-- sas/protection/ptoc.lua). Acceptable simplification at OC scale,
-- matching this codebase's established "don't over-engineer for OC
-- scale" philosophy (see e.g. sas/proto/goose.lua's/OC-IP-Stack's own
-- header comments on the same point).
--
-- Near-instantaneous (no time-grading accumulator, unlike PTOC) --
-- differential protection is a unit protection scheme that should
-- operate as fast as the scheme detects a real internal fault, which
-- this simplification models as "trip the instant restraint is
-- exceeded" rather than adding an artificial time delay.
--
-- Zero OC-API coupling, same testability rationale as curves.lua/ptoc.lua.
local pdif = {}

-- Validates one pdif scheme config. `resolvePoint(ref)` -> pointRecord|nil.
-- Deliberately requires exactly 2 inputs (HV/LV winding CTs) -- a real
-- 3-winding transformer's differential scheme needs a genuine 3-input
-- restraint calculation, which is out of scope here; config validation
-- rejects anything else rather than silently mis-evaluating it.
function pdif.validate(cfg, resolvePoint)
  if type(cfg.name) ~= "string" or cfg.name == "" then
    return nil, "protection.pdif: missing name"
  end
  if type(cfg.inputs) ~= "table" or #cfg.inputs ~= 2 then
    return nil, "protection.pdif[" .. cfg.name .. "]: inputs must have exactly 2 entries (HV/LV CTs)"
  end
  for i, input in ipairs(cfg.inputs) do
    local rec = type(input.ref) == "string" and resolvePoint(input.ref)
    if not rec or rec.type ~= "MV" then
      return nil, "protection.pdif[" .. cfg.name .. "]: inputs[" .. i .. "].ref must be an MV point: "
        .. tostring(input.ref)
    end
    if input.scale ~= nil and type(input.scale) ~= "number" then
      return nil, "protection.pdif[" .. cfg.name .. "]: inputs[" .. i .. "].scale must be a number"
    end
  end
  if type(cfg.minPickup) ~= "number" or cfg.minPickup < 0 then
    return nil, "protection.pdif[" .. cfg.name .. "]: minPickup must be a non-negative number"
  end
  if type(cfg.restraintSlope) ~= "number" or cfg.restraintSlope < 0 then
    return nil, "protection.pdif[" .. cfg.name .. "]: restraintSlope must be a non-negative number"
  end
  return true
end

-- `values` is a 2-element array of raw measured magnitudes parallel to
-- cfg.inputs (nil entries mean "currently invalid/unavailable"). Returns
-- true if the differential/restraint trip condition holds, false
-- otherwise (including whenever a reading is unavailable -- fail-safe
-- here would mean tripping on missing data, which is wrong for a scheme
-- that can only correctly assess a real internal fault by actually
-- comparing both currents; a stale/missing CT reading is instead the
-- kind of condition a separate comm/quality alarm should flag, not a
-- differential trip).
function pdif.evaluate(cfg, values)
  if values[1] == nil or values[2] == nil then return false end

  local scale1 = (cfg.inputs[1].scale or 1)
  local scale2 = (cfg.inputs[2].scale or 1)
  local scaled1 = values[1] * scale1
  local scaled2 = values[2] * scale2

  local diffCur = math.abs(scaled1 - scaled2)
  local restraintCur = (math.abs(scaled1) + math.abs(scaled2)) / 2

  return diffCur > cfg.minPickup and diffCur > cfg.restraintSlope * restraintCur
end

return pdif
