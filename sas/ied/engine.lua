-- sas.ied.engine: the generic, config-driven IED. Same daemon skeleton as
-- OC-IP-Stack's own ipstack.daemon (see that file's comments): start()
-- registers an event.timer tick callback and returns immediately;
-- tick() itself must stay entirely non-blocking (no os.sleep, no
-- timeoutSec>0 ipstack.socket call), matching daemon.lua's safeTick.
local event = require("event")
local socket = require("ipstack.socket")

local config = require("sas.config")
local model = require("sas.model")
local framing = require("sas.proto.framing")
local messages = require("sas.proto.messages")
local goose = require("sas.proto.goose")
local sbo = require("sas.sbo")
local io_rs = require("sas.io.redstone")
local meter = require("sas.io.meter")
local util = require("sas.util")

local engine = {}

local CFG_PATH = "/etc/sas-ied.cfg"

local DEFAULTS = {
  iedName = "IED1",
  logicalDevice = "LD0",
  mms = { port = 8102 },
  goose = { port = 8104, peers = {}, burstIntervalsSec = { 0.2, 0.5, 1, 2 }, heartbeatSec = 5 },
  tickIntervalSec = 0.2,
  integritySec = 30,
  points = {},
}

engine.state = {
  running = false,
  cfg = nil,
  db = nil,
  iedName = nil,
  listener = nil,
  clients = {},        -- array of { conn=, reader=, subs=nil|"*"|{[ref]=true} }
  gooseSock = nil,
  gooseState = nil,    -- goose.newPublisher(...)
  sbo = nil,
  pulses = {},          -- pending redstone pulses, see sas.io.redstone
  lastIntegrityAt = nil,
  tickTimerId = nil,
  log = {},
}

engine.log = util.makeLogger(engine.state.log, 200)

--- Point I/O ------------------------------------------------------------

local function readPointValue(rec)
  local io_ = rec.io
  if not io_ then return nil, "no io binding" end

  if io_.kind == "redstone" then
    if rec.type == "DPS" then
      return io_rs.readDouble(io_)
    elseif rec.type == "SPS" then
      local level, err = io_rs.readLevel(io_)
      if not level then return nil, err end
      return level >= (io_.onLevel or 1)
    end
    return nil, "redstone io binding on unsupported point type " .. tostring(rec.type)
  elseif io_.kind == "meter" then
    return meter.read(io_)
  end
  return nil, "unknown io kind: " .. tostring(io_.kind)
end

local function valueChangedEnough(rec, newValue)
  if rec.type == "MV" then
    if rec.value == nil then return true end
    return math.abs(newValue - rec.value) >= (rec.deadband or 0)
  end
  return rec.value ~= newValue
end

--- Client connection handling ------------------------------------------------------------

local function sendMsg(client, msg)
  local frame, err = framing.encode(msg)
  if not frame then
    engine.log("warn", "ied: could not encode message: %s", tostring(err))
    return
  end
  client.conn:send(frame)
end

local function handleGetModel(client, msg)
  local points = {}
  model.eachPoint(engine.state.db, function(_, rec)
    table.insert(points, { ln = rec.ln, doName = rec.doName, type = rec.type })
  end)
  sendMsg(client, messages.replyTo(msg, { ld = engine.state.db.ld, points = points }))
end

local function handleRead(client, msg)
  local values = {}
  for _, ref in ipairs(msg.refs or {}) do
    local rec = engine.state.db.points[ref]
    if rec then
      values[ref] = { value = rec.value, quality = rec.quality, t = rec.lastChangeAt }
    end
  end
  sendMsg(client, messages.replyTo(msg, { values = values }))
end

local function handleSubscribe(client, msg)
  if msg.refs == "*" then
    client.subs = "*"
  else
    local subs = {}
    for _, ref in ipairs(msg.refs or {}) do subs[ref] = true end
    client.subs = subs
  end
  sendMsg(client, messages.replyTo(msg, {}))
end

local function handleSelect(client, msg)
  local rec = engine.state.db.points[msg.ref]
  if not rec or not model.CONTROL_TYPES[rec.type] then
    sendMsg(client, messages.replyTo(msg, { ok = false, err = "not a control point: " .. tostring(msg.ref) }))
    return
  end
  local timeoutSec = (rec.sbo and rec.sbo.timeoutSec) or 30
  local token, err = engine.state.sbo:select(msg.ref, msg.clientId, timeoutSec, computer.uptime())
  if not token then
    sendMsg(client, messages.replyTo(msg, { ok = false, err = err }))
    return
  end
  sendMsg(client, messages.replyTo(msg, { ok = true, token = token }))
end

local function applyOperate(rec, value)
  if rec.type == "DPC" then
    return io_rs.operateDouble(engine.state.pulses, rec.io, value, computer.uptime())
  elseif rec.type == "SPC" then
    return io_rs.writeLevel(rec.io, value)
  end
  return nil, "unsupported control type: " .. tostring(rec.type)
end

local function handleOperate(client, msg)
  local rec = engine.state.db.points[msg.ref]
  if not rec or not model.CONTROL_TYPES[rec.type] then
    sendMsg(client, messages.replyTo(msg, { ok = false, err = "not a control point: " .. tostring(msg.ref) }))
    return
  end

  local ok, err = engine.state.sbo:operate(msg.ref, msg.token, msg.clientId, computer.uptime())
  if not ok then
    sendMsg(client, messages.replyTo(msg, { ok = false, err = err }))
    return
  end

  local applyOk, applyErr = applyOperate(rec, msg.value)
  if not applyOk then
    sendMsg(client, messages.replyTo(msg, { ok = false, err = applyErr or "operate failed" }))
    return
  end
  sendMsg(client, messages.replyTo(msg, { ok = true }))
end

local function handleCancel(client, msg)
  local ok, err = engine.state.sbo:cancel(msg.ref, msg.token, msg.clientId, computer.uptime())
  sendMsg(client, messages.replyTo(msg, { ok = ok and true or false, err = err }))
end

local function handleHeartbeat(client, msg)
  sendMsg(client, messages.replyTo(msg, {}))
end

local HANDLERS = {
  ["get-model"] = handleGetModel,
  read = handleRead,
  subscribe = handleSubscribe,
  select = handleSelect,
  operate = handleOperate,
  cancel = handleCancel,
  heartbeat = handleHeartbeat,
}

local function dispatch(client, msg)
  local handler = HANDLERS[msg.type]
  if not handler then
    if messages.REQUEST_TYPES[msg.type] then
      sendMsg(client, messages.replyTo(msg, { ok = false, err = "not supported by an IED server" }))
    else
      engine.log("warn", "ied: unknown message type '%s'", tostring(msg.type))
    end
    return
  end
  local ok, err = pcall(handler, client, msg)
  if not ok then
    engine.log("error", "ied: handler error for '%s': %s", tostring(msg.type), tostring(err))
  end
end

--- Tick ------------------------------------------------------------

local function acceptClients()
  local conn = engine.state.listener:accept() -- no timeout arg: single non-blocking check
  while conn do
    table.insert(engine.state.clients, { conn = conn, reader = framing.newReader(), subs = nil })
    conn = engine.state.listener:accept()
  end
end

local function serviceClients()
  local clients = engine.state.clients
  local i = 1
  while i <= #clients do
    local client = clients[i]
    local dead = false

    local data, rerr = client.conn:receive(0) -- explicit 0: non-blocking, see sas.proto.mmsclient header
    if data == nil then
      dead = true
    elseif data ~= "" then
      client.reader:feed(data)
      while true do
        local msg, ferr = client.reader:pop()
        if ferr then dead = true; break end
        if not msg then break end
        dispatch(client, msg)
      end
    end

    if not dead and client.conn:state() == "CLOSED" then dead = true end

    if dead then
      pcall(function() client.conn:close() end)
      table.remove(clients, i)
    else
      i = i + 1
    end
  end
end

-- Polls every status/measured-value point's I/O binding, updates its live
-- value, and returns the list of refs that changed (or that are due for
-- a periodic integrity refresh even without a real change, so subscribed
-- reports/GOOSE never go silently stale on a genuinely static plant).
local function pollPoints(now)
  local changedRefs = {}
  local forceIntegrity = (not engine.state.lastIntegrityAt)
    or (now - engine.state.lastIntegrityAt >= (engine.state.cfg.integritySec or 30))

  model.eachPoint(engine.state.db, function(ref, rec)
    if rec.io and (model.STATUS_TYPES[rec.type] or rec.type == "MV") then
      local val, rerr = readPointValue(rec)
      if val ~= nil then
        local changed = valueChangedEnough(rec, val)
        model.setValue(rec, val, "good", now)
        if changed or forceIntegrity then
          table.insert(changedRefs, ref)
        end
      elseif rec.quality ~= "invalid" then
        rec.quality = "invalid"
        table.insert(changedRefs, ref)
      end
    end
  end)

  if forceIntegrity then engine.state.lastIntegrityAt = now end
  return changedRefs
end

local function deliverReports(changedRefs)
  if #changedRefs == 0 then return end
  for _, client in ipairs(engine.state.clients) do
    if client.subs then
      local values = {}
      for _, ref in ipairs(changedRefs) do
        if client.subs == "*" or client.subs[ref] then
          local rec = engine.state.db.points[ref]
          values[ref] = { value = rec.value, quality = rec.quality, t = rec.lastChangeAt }
        end
      end
      if next(values) then
        sendMsg(client, { type = "report", values = values })
      end
    end
  end
end

local function publishGoose(changedRefs, now)
  local dirty = false
  for _, ref in ipairs(changedRefs) do
    local rec = engine.state.db.points[ref]
    if rec.goose then dirty = true; break end
  end
  if dirty then
    engine.state.gooseState:markDirty(now)
  end

  if not engine.state.gooseState:dueSend(now) then return end

  local values = {}
  model.eachPoint(engine.state.db, function(ref, rec)
    if rec.goose then
      values[ref] = { v = rec.value, q = rec.quality }
    end
  end)
  local payload = goose.encode(engine.state.iedName, engine.state.db.ld,
    engine.state.gooseState.stNum, engine.state.gooseState.sqNum, now, values)
  local wire = goose.encodeWire(payload)

  for _, peer in ipairs(engine.state.cfg.goose.peers) do
    local ok, serr = engine.state.gooseSock:sendto(peer, engine.state.cfg.goose.port, wire)
    if not ok then
      engine.log("warn", "ied: goose send to %s failed: %s", tostring(peer), tostring(serr))
    end
  end
end

function engine.tick()
  local ok, err = pcall(function()
    local now = computer.uptime()

    acceptClients()
    serviceClients()

    local changedRefs = pollPoints(now)
    deliverReports(changedRefs)
    publishGoose(changedRefs, now)

    engine.state.sbo:tick(now)
    io_rs.pulseTick(engine.state.pulses, now)
  end)
  if not ok then
    engine.log("error", "ied: tick error: %s", tostring(err))
  end
end

--- Lifecycle ------------------------------------------------------------

-- Idempotent: calling start() while already running is a no-op success.
function engine.start()
  if engine.state.running then return true end

  local cfg, cfgErr = config.load(CFG_PATH, DEFAULTS)
  engine.state.cfg = cfg
  engine.log = util.makeLogger(engine.state.log, 200)
  if cfgErr then
    engine.log("warn", "ied: %s (using built-in defaults)", cfgErr)
  end

  local dbOk, dbResult = pcall(model.buildIedDatabase, cfg)
  if not dbOk then
    engine.log("error", "ied: invalid point configuration: %s", tostring(dbResult))
    return nil, tostring(dbResult)
  end
  engine.state.db = dbResult
  engine.state.iedName = cfg.iedName

  -- Fails loudly (no retry loop) if ipstackd isn't running -- matches
  -- ipstack.socket's own "never hang on a dead daemon" rule.
  local listener, lerr = socket.listen(cfg.mms.port)
  if not listener then
    engine.log("error", "ied: could not start MMS-lite listener: %s (is ipstackd running?)", tostring(lerr))
    return nil, lerr
  end
  engine.state.listener = listener

  local gooseSock, gerr = socket.udp()
  if not gooseSock then
    engine.log("error", "ied: could not open GOOSE socket: %s", tostring(gerr))
    pcall(function() listener:close() end)
    engine.state.listener = nil
    return nil, gerr
  end
  engine.state.gooseSock = gooseSock

  engine.state.clients = {}
  engine.state.pulses = {}
  engine.state.sbo = sbo.new()
  engine.state.gooseState = goose.newPublisher(cfg.goose)
  engine.state.lastIntegrityAt = nil

  engine.state.tickTimerId = event.timer(cfg.tickIntervalSec, engine.tick, math.huge)
  engine.state.running = true

  engine.log("info", "iedd started: %s/%s, mms port %d, %d point(s)",
    engine.state.iedName, cfg.logicalDevice, cfg.mms.port, util.countTable(engine.state.db.points))
  return true
end

-- Unregisters the tick timer, closes all connections/sockets. Idempotent.
function engine.stop()
  if not engine.state.running then return true end

  if engine.state.tickTimerId then
    event.cancel(engine.state.tickTimerId)
    engine.state.tickTimerId = nil
  end

  for _, client in ipairs(engine.state.clients) do
    pcall(function() client.conn:close() end)
  end
  engine.state.clients = {}

  if engine.state.listener then
    pcall(function() engine.state.listener:close() end)
    engine.state.listener = nil
  end
  if engine.state.gooseSock then
    pcall(function() engine.state.gooseSock:close() end)
    engine.state.gooseSock = nil
  end

  engine.state.running = false
  engine.log("info", "iedd stopped")
  return true
end

function engine.isRunning()
  return engine.state.running
end

return engine
