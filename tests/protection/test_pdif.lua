-- tests/protection/test_pdif.lua: executable unit test for
-- sas.protection.pdif's restraint math, runnable with plain `lua5.3`.
-- Run from the repo root:
--   lua5.3 tests/protection/test_pdif.lua
package.path = "./?.lua;" .. package.path
local pdif = require("sas.protection.pdif")

local failures = 0
local function check(cond, label)
  if cond then
    print("ok:   " .. label)
  else
    failures = failures + 1
    print("FAIL: " .. label)
  end
end

-- Through-load: HV=100A, LV scaled by turns ratio also reads ~100A ->
-- near-zero differential, well inside restraint -- must NOT trip.
local cfg = { inputs = { { ref = "MMXU1.Amp", scale = 1.0 }, { ref = "MMXU2.Amp", scale = 3.478 } },
              minPickup = 0.2, restraintSlope = 0.4 }
check(pdif.evaluate(cfg, { 100, 100 / 3.478 }) == false, "balanced through-load does not trip")

-- Internal fault: HV current stays ~100A but LV collapses to ~0 (fault
-- between the CTs) -- large differential, must trip.
check(pdif.evaluate(cfg, { 100, 0 }) == true, "internal fault (LV collapse) trips")

-- Small measurement noise/CT mismatch below minPickup must not trip even
-- though it's technically nonzero differential.
local cfgNoisy = { inputs = { { ref = "a", scale = 1 }, { ref = "b", scale = 1 } },
                    minPickup = 5, restraintSlope = 0.4 }
check(pdif.evaluate(cfgNoisy, { 100, 101 }) == false, "sub-minPickup noise does not trip")

-- A missing reading on either side never trips (see pdif.lua's doc
-- comment on why this is NOT treated as fail-safe-trip).
check(pdif.evaluate(cfg, { nil, 50 }) == false, "missing HV reading does not trip")
check(pdif.evaluate(cfg, { 50, nil }) == false, "missing LV reading does not trip")

-- Restraint slope actually restrains: a large through-current with a
-- proportionally larger absolute mismatch (but same relative mismatch)
-- should behave consistently under the slope, not trip on magnitude
-- alone.
local cfgSlope = { inputs = { { ref = "a", scale = 1 }, { ref = "b", scale = 1 } },
                    minPickup = 0.2, restraintSlope = 0.5 }
-- 2% mismatch at high current: diff=20, restraint=~990, slope*restraint=495 -- far below, no trip.
check(pdif.evaluate(cfgSlope, { 1000, 980 }) == false, "small relative mismatch at high current does not trip")
-- 60% mismatch: diff=480, restraint=~740, slope*restraint=370 -- diff exceeds, trips.
check(pdif.evaluate(cfgSlope, { 1000, 400 }) == true, "large relative mismatch trips")

if failures > 0 then
  print(string.format("\n%d assertion(s) FAILED", failures))
  os.exit(1)
end
print("\nall assertions passed")
