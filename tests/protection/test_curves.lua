-- tests/protection/test_curves.lua: executable unit test for
-- sas.protection.curves, runnable with plain `lua5.3` (not just
-- `luac5.3 -p` syntax-checking) since the module has zero OC-API
-- coupling by design. Run from the repo root:
--   lua5.3 -e "package.path = './?.lua;' .. package.path" tests/protection/test_curves.lua
-- Exits non-zero on any assertion failure.
package.path = "./?.lua;" .. package.path
local curves = require("sas.protection.curves")

local failures = 0

local function assertClose(got, want, tol, label)
  if got == nil or math.abs(got - want) > tol then
    failures = failures + 1
    print(string.format("FAIL: %s -- got %s, want %s (tol %s)", label, tostring(got), tostring(want), tostring(tol)))
  else
    print(string.format("ok:   %s -- %s", label, tostring(got)))
  end
end

local function assertNil(got, label)
  if got ~= nil then
    failures = failures + 1
    print(string.format("FAIL: %s -- got %s, want nil", label, tostring(got)))
  else
    print("ok:   " .. label)
  end
end

-- IEC 60255-151 curves: exact-fraction sanity checks (values chosen so
-- the formula simplifies to a value verifiable by hand).
assertClose(curves.timeToTrip("IEC_VERY_INVERSE", 2, 1), 13.5, 1e-9, "IEC_VERY_INVERSE M=2 tms=1 == 13.5/(M-1)")
assertClose(curves.timeToTrip("IEC_VERY_INVERSE", 1.5, 2), 54, 1e-9, "IEC_VERY_INVERSE M=1.5 tms=2 == 54")
assertClose(curves.timeToTrip("IEC_EXTREMELY_INVERSE", 2, 1), 80 / 3, 1e-9, "IEC_EXTREMELY_INVERSE M=2 tms=1 == 80/3")

-- IEC_STANDARD_INVERSE at M=10, tms=1: published/well-known reference
-- value (0.14/(10^0.02-1)) ~= 2.97s.
assertClose(curves.timeToTrip("IEC_STANDARD_INVERSE", 10, 1), 2.97, 0.02, "IEC_STANDARD_INVERSE M=10 tms=1")

-- IEEE C37.112 curves at M=2, tms=1: published reference values.
assertClose(curves.timeToTrip("IEEE_MOD_INVERSE", 2, 1), 3.80, 0.02, "IEEE_MOD_INVERSE M=2 tms=1")
assertClose(curves.timeToTrip("IEEE_VERY_INVERSE", 2, 1), 7.03, 0.02, "IEEE_VERY_INVERSE M=2 tms=1")
assertClose(curves.timeToTrip("IEEE_EXTREME_INVERSE", 2, 1), 9.52, 0.02, "IEEE_EXTREME_INVERSE M=2 tms=1")

-- Boundary/monotonicity properties, not just point values.
assertNil(curves.timeToTrip("IEC_VERY_INVERSE", 1, 1), "M==1 (at pickup, not over) returns nil")
assertNil(curves.timeToTrip("IEC_VERY_INVERSE", 0.5, 1), "M<1 (under pickup) returns nil")

local tHigh = curves.timeToTrip("IEC_STANDARD_INVERSE", 3, 1)
local tLow = curves.timeToTrip("IEC_STANDARD_INVERSE", 20, 1)
if not (tHigh and tLow and tHigh > tLow) then
  failures = failures + 1
  print(string.format("FAIL: IEC_STANDARD_INVERSE must trip faster at higher M -- got t(M=3)=%s, t(M=20)=%s",
    tostring(tHigh), tostring(tLow)))
else
  print(string.format("ok:   IEC_STANDARD_INVERSE monotonic decreasing (t(M=3)=%.3f > t(M=20)=%.3f)", tHigh, tLow))
end

-- Time multiplier scales linearly.
local base = curves.timeToTrip("IEEE_VERY_INVERSE", 3, 1)
local scaled = curves.timeToTrip("IEEE_VERY_INVERSE", 3, 2.5)
assertClose(scaled, base * 2.5, 1e-9, "time multiplier scales linearly")

-- Unknown curve name is a clean error, not a crash.
local ok, err = curves.timeToTrip("NOT_A_REAL_CURVE", 2, 1)
if ok ~= nil or not err then
  failures = failures + 1
  print("FAIL: unknown curve name should return nil, err")
else
  print("ok:   unknown curve name returns nil, err: " .. err)
end

if failures > 0 then
  print(string.format("\n%d assertion(s) FAILED", failures))
  os.exit(1)
end
print("\nall assertions passed")
