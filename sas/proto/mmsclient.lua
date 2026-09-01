-- sas.proto.mmsclient: shared non-blocking MMS-lite client, used both by
-- sas/scada/engine.lua (talking to IEDs) and the HMI (talking to SCADA)
-- -- same role, different peer.
--
-- IMPORTANT non-blocking discipline, confirmed against OC-IP-Stack's
-- actual source (ipstack/core.lua's waitUntil): conn:receive(timeoutSec)
-- checks its underlying predicate exactly once and returns immediately
-- if timeoutSec is falsy-or-<=0 -- but conn:receive() with NO argument
-- defaults to a 10s *blocking* wait (ipstack.socket's
-- DEFAULT_RECEIVE_TIMEOUT), because `timeoutSec or DEFAULT_RECEIVE_TIMEOUT`
-- only short-circuits on nil/false, and Lua treats 0 as truthy. So poll()
-- below always passes an explicit 0, never omits the argument.
local socket = require("ipstack.socket")
local framing = require("sas.proto.framing")
local messages = require("sas.proto.messages")

local mmsclient = {}

local Client = {}
Client.__index = Client

-- Connects (blocking up to timeoutSec, since this only happens at
-- startup/reconnect, never inside a tick) to targetIp:port. Returns a
-- Client, or nil, err.
function mmsclient.connect(targetIp, port, timeoutSec)
  local conn, err = socket.connect(targetIp, port, timeoutSec)
  if not conn then return nil, err end
  return setmetatable({
    conn = conn,
    reader = framing.newReader(),
    nextId = 1,
    pending = {},   -- [id] = true while awaiting a reply
    replies = {},   -- [id] = replyMsg, once arrived (popped by popReply)
    inbox = {},     -- queued unsolicited pushes (report/alarm-update)
    connected = true,
    lastError = nil,
  }, Client)
end

function Client:isConnected()
  if not self.connected then return false end
  local state = self.conn:state()
  if state == "CLOSED" then
    self.connected = false
  end
  return self.connected
end

-- Encodes and sends one request, assigning it a fresh id for reply
-- correlation. Returns the id, or nil, err.
function Client:sendRequest(msgWithoutId)
  local msg = {}
  for k, v in pairs(msgWithoutId) do msg[k] = v end
  msg.id = self.nextId
  self.nextId = self.nextId + 1

  local frame, ferr = framing.encode(msg)
  if not frame then return nil, ferr end

  local ok, err = self.conn:send(frame)
  if not ok then
    self.connected = false
    self.lastError = err
    return nil, err
  end
  self.pending[msg.id] = true
  return msg.id
end

function Client:dispatch(msg)
  if messages.isReply(msg) and msg.id ~= nil then
    self.replies[msg.id] = msg
    self.pending[msg.id] = nil
  elseif messages.isPush(msg) then
    table.insert(self.inbox, msg)
  end
  -- Anything else (malformed/unknown type) is silently dropped -- a
  -- future protocol version's client talking to an older peer, or vice
  -- versa, should degrade gracefully rather than error out.
end

-- Non-blocking: drains whatever has arrived on the underlying connection,
-- decodes complete frames, and dispatches each to either self.replies
-- (request/reply correlation, popped via popReply) or self.inbox
-- (unsolicited pushes, drained via drainInbox). Call this once per
-- tick/GUI-poll cycle. Returns true, or nil, err if the connection died
-- (caller should reconnect).
function Client:poll()
  if not self.connected then return nil, self.lastError or "not connected" end

  local data, err = self.conn:receive(0) -- explicit 0: see file header
  if data == nil then
    self.connected = false
    self.lastError = err
    return nil, err
  end
  if data ~= "" then
    self.reader:feed(data)
    while true do
      local msg, ferr = self.reader:pop()
      if ferr then
        self.connected = false
        self.lastError = ferr
        return nil, ferr
      end
      if not msg then break end
      self:dispatch(msg)
    end
  end
  return true
end

-- Non-blocking: returns and clears the reply for `id` if it has arrived,
-- else nil.
function Client:popReply(id)
  local r = self.replies[id]
  if r then self.replies[id] = nil end
  return r
end

function Client:hasPending(id)
  return self.pending[id] == true
end

-- Non-blocking: returns and clears all queued unsolicited pushes.
function Client:drainInbox()
  local items = self.inbox
  self.inbox = {}
  return items
end

-- Blocking convenience: send a request and wait (polling + os.sleep)
-- up to timeoutSec for its reply. ONLY for foreground/manual use
-- (usr/bin/sas-ctl.lua) -- never call this from inside a daemon tick,
-- which must stay non-blocking end to end.
function Client:request(msg, timeoutSec)
  timeoutSec = timeoutSec or 10
  local id, err = self:sendRequest(msg)
  if not id then return nil, err end

  local deadline = computer.uptime() + timeoutSec
  while computer.uptime() < deadline do
    local ok, perr = self:poll()
    if not ok then return nil, perr end
    local reply = self:popReply(id)
    if reply then return reply end
    os.sleep(0.1)
  end
  return nil, "timeout"
end

function Client:close()
  self.connected = false
  return self.conn:close()
end

mmsclient.Client = Client

return mmsclient
