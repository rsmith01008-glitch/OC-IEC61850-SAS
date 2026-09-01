-- tests/protection/test_ptoc.lua: executable unit test for
-- sas.protection.ptoc's tick accumulator, runnable with plain `lua5.3`.
-- Run from the repo root:
--   lua5.3 tests/protection/test_ptoc.lua
package.path = "./?.lua;" .. package.path
local ptoc = require("sas.protection.ptoc")

local failures = 0
local function check(cond, label)
  if cond then
    print("ok:   " .. label)
  else
    failures = failures + 1
    print("FAIL: " .. label)
  end
end

-- IEC_VERY_INVERSE at M=2, tms=1 trips in exactly 13.5s of constant
-- overcurrent (see test_curves.lua). Feeding dt=1.35s ticks for 10 ticks
-- should land the accumulator just at/over 1 on the 10th tick, not
-- earlier or (much) later.
local cfg = { pickup = 10, curve = "IEC_VERY_INVERSE", timeMultiplier = 1, resetSec = 0.1 }
local state = ptoc.newState()
local trippedAtTick = nil
for i = 1, 20 do
  local tripped = ptoc.tick(state, cfg, 20, 1.35) -- measured=20 -> M=2
  if tripped then
    trippedAtTick = i
    break
  end
end
-- Exactly 10 ticks of 1.35s is the mathematical boundary (10*1.35=13.5);
-- floating-point rounding can legitimately land the accumulator just
-- under 1.0 at tick 10, tripping on tick 11 instead -- allow either.
check(trippedAtTick == 10 or trippedAtTick == 11,
  "constant M=2 overcurrent trips at the 13.5s boundary, tick 10 or 11 of 1.35s (got tick "
    .. tostring(trippedAtTick) .. ")")

-- Below pickup never trips and the accumulator decays back toward 0.
local cfg2 = { pickup = 10, curve = "IEC_VERY_INVERSE", timeMultiplier = 1, resetSec = 1 }
local state2 = ptoc.newState()
ptoc.tick(state2, cfg2, 20, 5) -- push some accumulation while over pickup
local accumBefore = state2.accum
check(accumBefore > 0, "accumulator builds up while over pickup")
for _ = 1, 20 do
  ptoc.tick(state2, cfg2, 5, 1) -- now under pickup (M=0.5)
end
check(state2.accum == 0, "accumulator decays fully back to 0 once held under pickup (got " .. tostring(state2.accum) .. ")")

-- A missing/invalid reading (nil) never trips and doesn't touch the
-- accumulator (a momentary bad read shouldn't erase real accumulated
-- operate-time -- see ptoc.lua's tick() doc comment).
local cfg3 = { pickup = 10, curve = "IEC_VERY_INVERSE", timeMultiplier = 1, resetSec = 1 }
local state3 = ptoc.newState()
ptoc.tick(state3, cfg3, 20, 5)
local accumBefore3 = state3.accum
local trippedOnNil = ptoc.tick(state3, cfg3, nil, 5)
check(trippedOnNil == false, "nil measurement never trips")
check(state3.accum == accumBefore3, "nil measurement doesn't change the accumulator")

-- DEFINITE_TIME: trips at exactly definiteTimeSec regardless of M
-- (as long as M>1), no curve-shape math involved.
local cfgDt = { pickup = 10, curve = "DEFINITE_TIME", definiteTimeSec = 3 }
local stateDt = ptoc.newState()
local trippedAtTickDt = nil
for i = 1, 10 do
  if ptoc.tick(stateDt, cfgDt, 50, 1) then trippedAtTickDt = i; break end
end
check(trippedAtTickDt == 3, "DEFINITE_TIME trips on tick 3 of 1s ticks with definiteTimeSec=3 (got "
  .. tostring(trippedAtTickDt) .. ")")

if failures > 0 then
  print(string.format("\n%d assertion(s) FAILED", failures))
  os.exit(1)
end
print("\nall assertions passed")
