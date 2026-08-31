-- sas.io.meter: analog measurement binding for Create: Electro-Energistics
-- meter blocks (voltmeters/ammeters), read via an OpenComputers Adapter
-- block bridging the block's ComputerCraft peripheral onto the OC
-- component network.
--
-- Verified against the mod's actual source
-- (github.com/george8188625/Create-Electro-Energetics, commit
-- 6f8adef55242dc5169639c314272ee66027cba0d):
-- compat/computercraft/peripherals/ElectricGaugePeripheral.java exposes
-- gauge readings ONLY via ComputerCraft's peripheral API (SyncedPeripheral
-- + dan200.computercraft.api.lua.LuaFunction) -- there is no
-- OpenComputers-native package anywhere in that repo. Reaching it from OC
-- therefore requires an OpenComputers **Adapter** block placed against the
-- physical voltmeter/ammeter block; verified this bridge mechanism against
-- OpenComputers' own source (li.cil.oc.integration.computercraft.DriverPeripheral):
-- the Adapter creates one OC component per attached CC peripheral, whose
-- methods() is exactly the peripheral's own getMethodNames() and whose
-- invoke() forwards straight to the peripheral's callMethod() -- so
-- component.invoke(address, method) below really does call the CC
-- peripheral's Lua function verbatim, once the Adapter is in place.
--
-- The mod exposes a SINGLE shared method, getValue(), for BOTH voltmeter
-- and ammeter blocks -- which quantity it returns depends on the physical
-- block itself, not on the method name -- so a voltmeter and an ammeter
-- are two separate Adapter-bridged addresses both called with
-- method = "getValue", not two methods on one shared address. getValue()
-- also bakes in that block's own in-world display-scale dial
-- (ElectricGaugeBlockEntity.scaling) -- see etc/sas-ied.cfg.example for
-- the full config shape and that operational caveat. This was verified
-- against OpenComputers' mainline bridge source, not by running it
-- in-game -- spot-check component.list()/component.proxy(addr).getMethods()
-- against your actual modpack's OpenComputers build before relying on it.
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
