-- sas.protection.ptoc: time-overcurrent protection (IEC 61850 PTOC),
-- working trip logic driven by a magnitude-only current measurement
-- (Create: Electro-Energistics meters have no phase-angle data source --
-- see sas/io/meter.lua's header -- but a plain overcurrent scheme only
-- ever needs magnitude, unlike distance protection).
--
-- Uses the standard "percentage operate time" accumulator model real
-- IDMT relays use to generalize a curve's constant-current trip time to
-- fluctuating load: each tick adds dt/timeToTrip(M) to an accumulator
-- (so a current held exactly at the curve's characteristic value trips
-- in exactly one curve-time's worth of ticks), and resets proportionally
-- while below pickup. Zero OC-API coupling here either -- state is a
-- plain table the caller (sas/ied/engine.lua) owns and persists across
-- ticks; this module only computes state transitions.
local curves = require("sas.protection.curves")

local ptoc = {}

-- Validates one ptoc scheme config against the IED's point database.
-- `resolvePoint(ref)` -> pointRecord|nil (caller supplies so this module
-- doesn't need to know sas.model's db shape). Returns true, or nil, err.
function ptoc.validate(cfg, resolvePoint, isControlType)
  if type(cfg.name) ~= "string" or cfg.name == "" then
    return nil, "protection.ptoc: missing name"
  end
  local inputRec = type(cfg.input) == "string" and resolvePoint(cfg.input)
  if not inputRec or inputRec.type ~= "MV" then
    return nil, "protection.ptoc[" .. cfg.name .. "]: input must be an MV point: " .. tostring(cfg.input)
  end
  local tripRec = type(cfg.trip) == "string" and resolvePoint(cfg.trip)
  if not tripRec or not isControlType(tripRec.type) then
    return nil, "protection.ptoc[" .. cfg.name .. "]: trip must be a control point: " .. tostring(cfg.trip)
  end
  if type(cfg.pickup) ~= "number" or cfg.pickup <= 0 then
    return nil, "protection.ptoc[" .. cfg.name .. "]: pickup must be a positive number"
  end
  if cfg.curve == "DEFINITE_TIME" then
    if type(cfg.definiteTimeSec) ~= "number" or cfg.definiteTimeSec < 0 then
      return nil, "protection.ptoc[" .. cfg.name .. "]: DEFINITE_TIME curve needs definiteTimeSec"
    end
  elseif not curves.isKnown(cfg.curve) then
    return nil, "protection.ptoc[" .. cfg.name .. "]: unknown curve " .. tostring(cfg.curve)
  end
  return true
end

function ptoc.newState()
  return { accum = 0 }
end

local function tripTime(cfg, M)
  if cfg.curve == "DEFINITE_TIME" then
    if M and M > 1 then return cfg.definiteTimeSec end
    return nil
  end
  return curves.timeToTrip(cfg.curve, M, cfg.timeMultiplier or 1)
end

-- Advances `state` by `dt` seconds given the current `measured` magnitude
-- (nil if the input point's reading is currently invalid/unavailable --
-- treated as "not overcurrent," matching a fail-safe read but NOT
-- resetting the accumulator, since a momentary bad read shouldn't erase
-- real accumulated operate-time). Returns true exactly once, the tick a
-- trip condition is reached (and resets the accumulator), false
-- otherwise.
function ptoc.tick(state, cfg, measured, dt)
  if measured == nil then return false end

  local M = measured / cfg.pickup
  if M > 1 then
    local total = tripTime(cfg, M)
    if total and total > 0 then
      state.accum = state.accum + dt / total
      if state.accum >= 1 then
        state.accum = 0
        return true
      end
    end
  else
    local resetSec = cfg.resetSec or 0.1
    state.accum = math.max(0, state.accum - dt / resetSec)
  end
  return false
end

return ptoc
