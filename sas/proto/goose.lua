-- sas.proto.goose: GOOSE-lite fast peer messaging over UDP.
--
-- Real IEC 61850 GOOSE is Ethernet-multicast. OC-IP-Stack has no
-- broadcast/multicast address concept anywhere (confirmed by reading its
-- ipstack/ip.lua: routing/ARP always resolve one specific host), so
-- publishing here means looping a unicast udp:sendto() over a configured
-- list of peer addresses instead. Everything else about the model --
-- stNum/sqNum change/retransmission counters, a fast retransmit burst
-- after a real change settling into a steady heartbeat -- mirrors real
-- GOOSE's reliability-over-lossy-transport behavior.
local serialization = require("serialization")

local goose = {}

-- UDP datagrams are already delivered as discrete units by ipstack.udp
-- (no stream framing needed, unlike sas.proto.framing's TCP use), so
-- these just wrap serialization.serialize/unserialize directly.
function goose.encodeWire(msgTable)
  return serialization.serialize(msgTable)
end

function goose.decodeWire(raw)
  local ok, msg = pcall(serialization.unserialize, raw)
  if not ok or type(msg) ~= "table" then return nil, "could not decode GOOSE datagram" end
  return msg
end

-- Encodes one GOOSE-lite dataset publication for iedName/ldName.
-- `values` is { [ref] = {v=, q=} }.
function goose.encode(iedName, ldName, stNum, sqNum, t, values)
  return {
    type = "goose",
    ied = iedName,
    ld = ldName,
    stNum = stNum,
    sqNum = sqNum,
    t = t,
    values = values,
  }
end

function goose.isValid(msg)
  return type(msg) == "table" and msg.type == "goose"
    and type(msg.ied) == "string" and type(msg.values) == "table"
    and type(msg.stNum) == "number" and type(msg.sqNum) == "number"
end

-- Publisher-side retransmit scheduler. Tracks stNum/sqNum and the next
-- due send time; callers (sas/ied/engine.lua) call markDirty() whenever a
-- GOOSE-flagged point changes, and dueSend(now) each tick to find out
-- whether to actually transmit.
local Publisher = {}
Publisher.__index = Publisher

function goose.newPublisher(cfg)
  return setmetatable({
    stNum = 0,
    sqNum = 0,
    burstIntervalsSec = cfg.burstIntervalsSec or { 0.2, 0.5, 1, 2 },
    heartbeatSec = cfg.heartbeatSec or 5,
    burstStep = nil,      -- index into burstIntervalsSec while retransmitting a change
    nextSendAt = 0,
    lastSendAt = nil,
  }, Publisher)
end

-- Marks that the dataset actually changed: bumps stNum, resets sqNum, and
-- restarts the fast retransmit burst from its first interval.
function Publisher:markDirty(now)
  self.stNum = self.stNum + 1
  self.sqNum = 0
  self.burstStep = 1
  self.nextSendAt = now
end

-- Returns true if a send is due right now, and advances internal
-- scheduling state as if that send is about to happen (caller is
-- expected to actually send immediately after a true return).
function Publisher:dueSend(now)
  if now < self.nextSendAt then return false end

  if self.burstStep and self.burstStep <= #self.burstIntervalsSec then
    local interval = self.burstIntervalsSec[self.burstStep]
    self.burstStep = self.burstStep + 1
    self.nextSendAt = now + interval
  else
    self.burstStep = nil
    self.nextSendAt = now + self.heartbeatSec
  end

  self.sqNum = self.sqNum + 1
  self.lastSendAt = now
  return true
end

-- Subscriber-side liveness tracking, one per publishing IED. Called on
-- every received GOOSE frame; sas/scada/engine.lua uses lastSeenAt to
-- decide when to mark that IED's GOOSE-sourced points stale.
function goose.newSubscriberState()
  return { lastStNum = nil, lastSqNum = nil, lastSeenAt = nil }
end

function goose.recordReceived(state, msg, now)
  state.lastStNum = msg.stNum
  state.lastSqNum = msg.sqNum
  state.lastSeenAt = now
end

function goose.isStale(state, now, staleAfterSec)
  if not state.lastSeenAt then return true end
  return (now - state.lastSeenAt) > staleAfterSec
end

goose.Publisher = Publisher

return goose
