-- sas.proto.framing: TCP message framing for the MMS-lite protocol.
-- ipstack TCP (see OC-IP-Stack's ipstack/tcp.lua/socket.lua) is a raw byte
-- stream with no message boundaries, so every message is wrapped in a
-- 4-byte big-endian length prefix. The payload itself is encoded with
-- OpenOS's `serialization` library (serialize/unserialize), matching the
-- config-file idiom already established by OC-IP-Stack rather than
-- inventing a bespoke binary struct -- MMS-lite messages are small,
-- infrequent relative to a modem's bandwidth, and benefit far more from
-- being trivially inspectable/debuggable than from wire compactness.
local serialization = require("serialization")

local framing = {}

local LEN_FMT = ">I4"
local LEN_SIZE = 4

-- Maximum accepted frame body size. Well under ipstack's default UDP
-- datagram cap and a TCP connection's practical throughput; guards a
-- misbehaving peer's length prefix from making a reader buffer
-- unbounded amounts of memory waiting for a frame that will never
-- complete.
framing.MAX_FRAME_SIZE = 65536

-- Encodes one message table as length-prefixed bytes ready for
-- conn:send().
function framing.encode(msgTable)
  local body = serialization.serialize(msgTable)
  if #body > framing.MAX_FRAME_SIZE then
    return nil, "message too large to frame (" .. #body .. " > " .. framing.MAX_FRAME_SIZE .. " bytes)"
  end
  return string.pack(LEN_FMT, #body) .. body
end

local Reader = {}
Reader.__index = Reader

-- Creates a stateful frame reader. Feed it raw bytes as they arrive from
-- conn:receive(); call pop() in a loop after every feed() since one
-- receive() chunk can contain zero, one, or several complete frames.
function framing.newReader()
  return setmetatable({ buf = "" }, Reader)
end

function Reader:feed(chunk)
  if chunk and chunk ~= "" then
    self.buf = self.buf .. chunk
  end
end

-- Pops and decodes the oldest complete frame from the buffer. Returns the
-- decoded message table, or nil if not enough data has arrived yet, or
-- nil, err if the buffer is corrupt (oversized length prefix) or a frame
-- body fails to deserialize.
function Reader:pop()
  if #self.buf < LEN_SIZE then return nil end
  local len = string.unpack(LEN_FMT, self.buf)
  if len > framing.MAX_FRAME_SIZE then
    return nil, "peer sent an oversized frame length (" .. len .. " bytes)"
  end
  if #self.buf < LEN_SIZE + len then return nil end

  local body = self.buf:sub(LEN_SIZE + 1, LEN_SIZE + len)
  self.buf = self.buf:sub(LEN_SIZE + len + 1)

  local ok, msg = pcall(serialization.unserialize, body)
  if not ok or type(msg) ~= "table" then
    return nil, "could not decode frame body"
  end
  return msg
end

return framing
