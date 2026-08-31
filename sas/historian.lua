-- sas.historian: append-only event log with size-based rotation and a
-- simple linear-scan query, used by SCADA to record point-value
-- transitions and alarm events for the HMI's history/trend view.
--
-- Deliberately unindexed (matches OC-IP-Stack's own stated "don't
-- over-engineer for OpenComputers scale" design philosophy) -- a linear
-- scan over a handful of rotated log files is more than adequate for the
-- data volumes a substation-scale point count produces.
local filesystem = require("filesystem")
local serialization = require("serialization")

local historian = {}

local CURRENT_NAME = "events.log"

local function currentPath(dir)
  return filesystem.concat(dir, CURRENT_NAME)
end

local function rotatedPath(dir, n)
  return filesystem.concat(dir, CURRENT_NAME .. "." .. n)
end

local function ensureDir(dir)
  if not filesystem.exists(dir) then
    filesystem.makeDirectory(dir)
  end
end

-- Rotates events.log -> events.log.1 -> ... -> events.log.maxFiles,
-- dropping the oldest, if the current file has reached maxBytes.
local function maybeRotate(dir, maxBytes, maxFiles)
  local cur = currentPath(dir)
  if not filesystem.exists(cur) then return end
  if filesystem.size(cur) < maxBytes then return end

  local oldest = rotatedPath(dir, maxFiles)
  if filesystem.exists(oldest) then filesystem.remove(oldest) end
  for n = maxFiles - 1, 1, -1 do
    local from = rotatedPath(dir, n)
    if filesystem.exists(from) then
      filesystem.rename(from, rotatedPath(dir, n + 1))
    end
  end
  filesystem.rename(cur, rotatedPath(dir, 1))
end

-- Appends one event (a plain Lua table -- caller should include at least
-- `t` (computer.uptime()) and `type`) to the historian, rotating first if
-- the current file has grown past `maxBytes`.
function historian.append(dir, event, maxBytes, maxFiles)
  ensureDir(dir)
  maybeRotate(dir, maxBytes or 262144, maxFiles or 5)

  local f, err = io.open(currentPath(dir), "a")
  if not f then return nil, "could not open historian log: " .. tostring(err) end
  f:write(serialization.serialize(event) .. "\n")
  f:close()
  return true
end

-- Returns the list of files to scan, newest first: events.log, then
-- events.log.1, events.log.2, ... up to maxFiles.
local function filesNewestFirst(dir, maxFiles)
  local files = {}
  if filesystem.exists(currentPath(dir)) then
    table.insert(files, currentPath(dir))
  end
  for n = 1, maxFiles do
    local p = rotatedPath(dir, n)
    if filesystem.exists(p) then table.insert(files, p) end
  end
  return files
end

-- Scans the historian newest-file-first, newest-line-first within each
-- file, calling filterFn(event) -> bool for each decoded event, until
-- `limit` matches are found or every file is exhausted. Returns the
-- matches (newest first).
function historian.query(dir, filterFn, limit, maxFiles)
  limit = limit or 100
  local matches = {}
  for _, path in ipairs(filesNewestFirst(dir, maxFiles or 5)) do
    local f = io.open(path, "r")
    if f then
      local lines = {}
      for line in f:lines() do table.insert(lines, line) end
      f:close()
      for i = #lines, 1, -1 do
        local ok, event = pcall(serialization.unserialize, lines[i])
        if ok and type(event) == "table" and (not filterFn or filterFn(event)) then
          table.insert(matches, event)
          if #matches >= limit then return matches end
        end
      end
    end
  end
  return matches
end

return historian
