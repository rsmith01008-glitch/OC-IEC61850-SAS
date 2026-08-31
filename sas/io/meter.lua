-- sas.io.meter: analog measurement binding for Create: Electro-Energistics
-- meter blocks (voltmeters/ammeters), read via their OpenComputers
-- component bridge.
--
-- RISK / ASSUMPTION, flagged per the implementation plan: the exact OC
-- component method name(s) Create: Electro-Energistics exposes for
-- reading a meter's value cannot be verified outside the actual mod/game.
-- The binding is therefore deliberately generic -- `address` (component
-- address) and `method` (method name string) both come from
-- /etc/sas-ied.cfg, not hardcoded here -- so confirming the real method
-- name in-game (e.g. by printing component.proxy(addr).getMethods()) is a
-- one-line config edit, not a code change. See etc/sas-ied.cfg.example
-- for the config shape.
local component = require("component")

local meter = {}

-- Reads one analog value via component.invoke(binding.address,
-- binding.method). `binding.args`, if present, is a list of extra
-- arguments passed after the method name (some component methods take
-- parameters, e.g. a channel/side index). Returns the numeric value, or
-- nil, err.
function meter.read(binding)
  local args = binding.args or {}
  local ok, value = pcall(component.invoke, binding.address, binding.method, table.unpack(args))
  if not ok then
    return nil, "meter read failed (" .. tostring(binding.address) .. "." .. tostring(binding.method) .. "): " .. tostring(value)
  end
  if type(value) ~= "number" then
    return nil, "meter method did not return a number (got " .. type(value) .. ")"
  end
  return value
end

return meter
