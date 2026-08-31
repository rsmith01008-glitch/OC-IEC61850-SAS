-- sas-ctl: small CLI for inspecting a running iedd or scadad daemon's
-- state on this machine. Mirrors OC-IP-Stack's own usr/bin/ipstack-ctl.lua
-- -- reads the engine's shared module state directly (no IPC needed, same
-- require()-caching argument as ipstack.core), rather than only one of
-- iedd/scadad being possible per machine we just check whichever is
-- actually running.
local iedEngine = require("sas.ied.engine")
local scadaEngine = require("sas.scada.engine")
local model = require("sas.model")
local util = require("sas.util")
local alarms = require("sas.alarms")

local args = { ... }
local cmd = args[1] or "status"

local function printf(fmt, ...)
  print(string.format(fmt, ...))
end

-- Returns "ied", iedEngine or "scada", scadaEngine for whichever is
-- actually running on this machine, or nil if neither is.
local function activeEngine()
  if iedEngine.isRunning() then return "ied", iedEngine end
  if scadaEngine.isRunning() then return "scada", scadaEngine end
  return nil
end

local function cmdStatus()
  local kind, eng = activeEngine()
  if not kind then
    print("neither iedd nor scadad is running on this machine")
    return
  end
  if kind == "ied" then
    printf("iedd: running (%s/%s), %d point(s), %d client(s)",
      tostring(eng.state.iedName), tostring(eng.state.cfg.logicalDevice),
      util.countTable(eng.state.db.points), #eng.state.clients)
  else
    printf("scadad: running, %d configured IED(s), %d HMI client(s)",
      util.countTable(eng.state.iedClients), #eng.state.hmiClients)
  end
end

local function cmdPoints()
  local kind, eng = activeEngine()
  if not kind then
    print("no sas daemon running")
    return
  end
  if kind == "ied" then
    model.eachPoint(eng.state.db, function(ref, rec)
      printf("%-20s %-4s value=%-12s quality=%-8s goose=%s",
        ref, rec.type, tostring(rec.value), rec.quality, tostring(rec.goose))
    end)
  else
    model.eachAggregatePoint(eng.state.db, function(iedName, ref, rec)
      printf("%-14s %-20s %-4s value=%-12s quality=%-8s",
        iedName, ref, rec.type, tostring(rec.value), rec.quality)
    end)
  end
end

local function cmdAlarms()
  local kind, eng = activeEngine()
  if kind ~= "scada" then
    print("alarms are only tracked by scadad")
    return
  end
  local arr = alarms.toArray(eng.state.alarmList)
  if #arr == 0 then
    print("(no active or unacknowledged alarms)")
    return
  end
  for _, a in ipairs(arr) do
    printf("[%s] %-6s %s -- %s%s", a.id, a.severity, a.active and "ACTIVE" or "cleared",
      a.message, a.acked and " (acked)" or "")
  end
end

local function cmdLog()
  local n = tonumber(args[2]) or 20
  local kind, eng = activeEngine()
  if not kind then
    print("no sas daemon running")
    return
  end
  local log = eng.state.log
  local total = #log
  local from = math.max(1, total - n + 1)
  for i = from, total do
    local entry = log[i]
    printf("[%s] %s", entry.level, entry.message)
  end
end

local commands = {
  status = cmdStatus,
  points = cmdPoints,
  alarms = cmdAlarms,
  log = cmdLog,
}

local fn = commands[cmd]
if not fn then
  print("usage: sas-ctl <status|points|alarms|log [n]>")
  return 1
end
fn()
