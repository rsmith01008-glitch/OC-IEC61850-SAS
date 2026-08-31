-- sas.io.redstone: redstone I/O bindings for breaker/switch status and
-- control points, via OpenComputers' `redstone`-type component
-- (component.proxy(address):getInput(side)/:setOutput(side, level)).
-- Side numbers follow OpenComputers' `sides` convention (0-5).
--
-- A single redstone level can't natively express "operate open" vs
-- "operate closed" on one wire, so DPC control bindings use two distinct
-- output sides (tripSide/closeSide) with a momentary pulse, the same way
-- a real breaker's trip/close coils are two separate circuits.
local component = require("component")

local io_rs = {}

local function proxyFor(binding)
  local ok, proxy = pcall(component.proxy, binding.address)
  if not ok or not proxy then return nil, "redstone component not found: " .. tostring(binding.address) end
  return proxy
end

-- Reads a single side's level (0-15). Returns level, or nil, err.
function io_rs.readLevel(binding)
  local proxy, err = proxyFor(binding)
  if not proxy then return nil, err end
  local ok, level = pcall(proxy.getInput, binding.side)
  if not ok then return nil, "redstone read failed: " .. tostring(level) end
  return level
end

-- Reads a double-point status from two sides (openSide/closedSide).
-- Returns "open", "closed", "intermediate" (neither energized -- point in
-- transit), or "bad" (both energized -- an inconsistent/faulted state),
-- or nil, err on a read failure.
function io_rs.readDouble(binding)
  local proxy, err = proxyFor(binding)
  if not proxy then return nil, err end
  local ok1, openLvl = pcall(proxy.getInput, binding.openSide)
  local ok2, closedLvl = pcall(proxy.getInput, binding.closedSide)
  if not ok1 or not ok2 then return nil, "redstone read failed" end

  local openOn = openLvl > 0
  local closedOn = closedLvl > 0
  if openOn and closedOn then return "bad" end
  if openOn then return "open" end
  if closedOn then return "closed" end
  return "intermediate"
end

-- Writes a simple on/off output (SPC control / GGIO). `level` is a
-- boolean or a 0-15 number.
function io_rs.writeLevel(binding, level)
  local proxy, err = proxyFor(binding)
  if not proxy then return nil, err end
  local numLevel = level
  if type(level) == "boolean" then numLevel = level and 15 or 0 end
  local ok, werr = pcall(proxy.setOutput, binding.side, numLevel)
  if not ok then return nil, "redstone write failed: " .. tostring(werr) end
  return true
end

-- Starts a momentary output pulse on `side` (energizes it, then schedules
-- it to be cleared by pulseTick() after binding.pulseMs). `pending` is
-- the caller's own table of in-flight pulses (kept per-engine, not
-- module-global, so multiple engines/tests don't share state); each
-- entry is { address=, side=, resetAt= }.
function io_rs.pulseStart(pending, binding, side, now)
  local proxy, err = proxyFor(binding)
  if not proxy then return nil, err end
  local ok, werr = pcall(proxy.setOutput, side, 15)
  if not ok then return nil, "redstone write failed: " .. tostring(werr) end
  local pulseMs = binding.pulseMs or 250
  table.insert(pending, { address = binding.address, side = side, resetAt = now + (pulseMs / 1000) })
  return true
end

-- Called every engine tick: clears (sets back to 0) any pulse whose
-- resetAt has passed, and removes it from `pending`.
function io_rs.pulseTick(pending, now)
  local i = 1
  while i <= #pending do
    local p = pending[i]
    if p.resetAt <= now then
      local ok, proxy = pcall(component.proxy, p.address)
      if ok and proxy then
        pcall(proxy.setOutput, p.side, 0)
      end
      table.remove(pending, i)
    else
      i = i + 1
    end
  end
end

-- Applies a DPC control operate: value is "open" or "closed", pulsing
-- binding.tripSide or binding.closeSide respectively.
function io_rs.operateDouble(pending, binding, value, now)
  if value == "open" then
    return io_rs.pulseStart(pending, binding, binding.tripSide, now)
  elseif value == "closed" then
    return io_rs.pulseStart(pending, binding, binding.closeSide, now)
  end
  return nil, "invalid DPC operate value (expected 'open' or 'closed'): " .. tostring(value)
end

return io_rs
