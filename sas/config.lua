-- sas.config: generic /etc/*.cfg load/save with deep-merge-defaults,
-- mirroring ipstack.config's pattern (see OC-IP-Stack's ipstack/config.lua)
-- but parametrized over path+defaults so it's shared by sas-ied, sas-scada
-- and sas-hmi instead of being duplicated three times.
local serialization = require("serialization")

local config = {}

-- Recursively fills any key missing from `tbl` with the value from
-- `defaults`, without touching keys `tbl` already sets. Returns tbl.
local function deepMergeDefaults(tbl, defaults)
  for k, defaultV in pairs(defaults) do
    local curV = tbl[k]
    if curV == nil then
      if type(defaultV) == "table" then
        tbl[k] = deepMergeDefaults({}, defaultV)
      else
        tbl[k] = defaultV
      end
    elseif type(curV) == "table" and type(defaultV) == "table" then
      deepMergeDefaults(curV, defaultV)
    end
  end
  return tbl
end

-- Returns a fresh deep copy of `defaults`.
function config.newDefaults(defaults)
  return deepMergeDefaults({}, defaults)
end

-- Loads `path`, deep-merging in any keys missing from the file so a
-- partial/hand-edited config never crashes a reader that expects every
-- defaults key to exist. Returns the config table, or
-- config.newDefaults(defaults) plus an error string if the file is
-- missing or unparsable.
function config.load(path, defaults)
  local f, openErr = io.open(path, "r")
  if not f then
    return config.newDefaults(defaults), "could not open " .. path .. ": " .. tostring(openErr)
  end
  local raw = f:read("*a")
  f:close()

  local ok, tbl = pcall(serialization.unserialize, raw)
  if not ok or type(tbl) ~= "table" then
    return config.newDefaults(defaults), "could not parse " .. path .. " (invalid Lua table literal)"
  end

  return deepMergeDefaults(tbl, defaults)
end

-- Writes `tbl` to `path` via serialization.serialize. Returns true, or
-- nil+err on failure.
function config.save(tbl, path)
  local f, openErr = io.open(path, "w")
  if not f then
    return nil, "could not open " .. path .. " for writing: " .. tostring(openErr)
  end
  f:write(serialization.serialize(tbl, true))
  f:close()
  return true
end

return config
