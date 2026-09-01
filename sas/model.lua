-- sas.model: IEC 61850-inspired point naming and data model helpers,
-- shared by the IED, SCADA and HMI. Not a byte-perfect implementation of
-- the real standard's data model (no full SCL/ACSI object hierarchy) --
-- just enough of the LD/LN/DO naming convention and point-record shape to
-- give every layer a consistent vocabulary, matching OC-IP-Stack's own
-- "don't over-engineer for OC scale" philosophy.
--
-- Point types (loosely matching IEC 61850 common data classes):
--   SPS = single point status (boolean status, e.g. a simple indicator)
--   DPS = double point status (open/closed/intermediate/bad -- breakers/switches)
--   SPC = single point control (simple on/off output)
--   DPC = double point control (trip/close -- breakers/switches)
--   MV  = measured (analog) value
local model = {}

model.VALID_TYPES = { SPS = true, DPS = true, SPC = true, DPC = true, MV = true }
model.CONTROL_TYPES = { SPC = true, DPC = true }
model.STATUS_TYPES = { SPS = true, DPS = true }

-- IED-local point reference: "<LN>.<DOName>", e.g. "XCBR1.Pos".
function model.ref(ln, doName)
  return ln .. "." .. doName
end

-- Fully qualified, SCADA/HMI-facing reference:
-- "<iedName>/<ldName>/<LN>.<DOName>", e.g. "IED-BRK1/LD0/XCBR1.Pos".
function model.fullRef(iedName, ldName, ln, doName)
  return iedName .. "/" .. ldName .. "/" .. model.ref(ln, doName)
end

-- Splits a fully qualified reference back into its parts. Returns
-- iedName, ldName, ln, doName, or nil, err if malformed.
function model.parseFullRef(full)
  local iedName, ldName, ln, doName = full:match("^([^/]+)/([^/]+)/([^.]+)%.(.+)$")
  if not iedName then
    return nil, "malformed point reference: " .. tostring(full)
  end
  return iedName, ldName, ln, doName
end

-- Splits an IED-local reference ("XCBR1.Pos") back into ln, doName, or
-- nil, err if malformed.
function model.splitRef(ref)
  local ln, doName = ref:match("^([^.]+)%.(.+)$")
  if not ln then
    return nil, "malformed point reference: " .. tostring(ref)
  end
  return ln, doName
end

-- A status CDC (SPS/DPS) and its control counterpart (SPC/DPC) for the
-- same physical point (e.g. a breaker's position status and its trip/
-- close control) are two separate point records sharing one `ln` --
-- they CANNOT share a `doName` too, since "LN.DOName" is the addressing
-- key (model.ref) and a collision would silently clobber one of them.
-- Convention used throughout this codebase: the control counterpart's
-- doName is the status doName + "Ctl" (e.g. status "Pos", control
-- "PosCtl" -- see etc/sas-ied.cfg.example's XCBR1.Pos/XCBR1.PosCtl).
--
-- Given a list of point descriptors {ln, doName, type, ...} that all
-- share one addressing scope (one IED's own points, or one IED's slice
-- of SCADA's aggregate), sets `refField` on each descriptor to
-- `refFn(ln, counterpartDoName)` -- letting a caller (e.g. an HMI) find
-- "click this status tile, but select/operate against THAT ref" without
-- string-guessing the "Ctl" suffix itself. `refFn(ln, doName)` builds
-- whatever ref format the caller needs (IED-local vs SCADA-facing
-- fullRef). Only pairs when a `ln` group has exactly one status and
-- exactly one control point; ambiguous or absent otherwise, left unset.
function model.computePointPairing(points, refField, refFn)
  local byLn = {}
  for _, p in ipairs(points) do
    local group = byLn[p.ln]
    if not group then group = {}; byLn[p.ln] = group end
    table.insert(group, p)
  end
  for ln, group in pairs(byLn) do
    local statusPt, controlPt, ambiguous = nil, nil, false
    for _, p in ipairs(group) do
      if model.STATUS_TYPES[p.type] then
        if statusPt then ambiguous = true else statusPt = p end
      elseif model.CONTROL_TYPES[p.type] then
        if controlPt then ambiguous = true else controlPt = p end
      end
    end
    if statusPt and controlPt and not ambiguous then
      statusPt[refField] = refFn(ln, controlPt.doName)
      controlPt[refField] = refFn(ln, statusPt.doName)
    end
  end
end

-- Builds an IED's own point database from its /etc/sas-ied.cfg contents.
-- Returns { ld = cfg.logicalDevice, points = { [ref] = pointRecord } }.
-- Each pointRecord carries the config point definition plus live-value
-- fields (value/quality/lastChangeAt/lastPublishedAt), initialized empty.
function model.buildIedDatabase(cfg)
  local db = { ld = cfg.logicalDevice, points = {} }
  for _, p in ipairs(cfg.points) do
    if not model.VALID_TYPES[p.type] then
      error("sas.model: invalid point type '" .. tostring(p.type) .. "' for " .. model.ref(p.ln, p.doName))
    end
    local ref = model.ref(p.ln, p.doName)
    db.points[ref] = {
      ln = p.ln,
      doName = p.doName,
      type = p.type,
      io = p.io,
      goose = p.goose and true or false,
      deadband = p.deadband or 0,
      sbo = p.sbo,
      value = nil,
      quality = "invalid",
      lastChangeAt = nil,
      lastPublishedAt = nil,
    }
  end
  return db
end

-- SCADA's aggregate database: one sub-database per configured IED, keyed
-- by iedName, populated at connect time from that IED's get-model-reply
-- (see sas/scada/engine.lua) rather than hand-duplicated in sas-scada.cfg.
function model.newAggregateDatabase()
  return { ieds = {} }
end

-- Ensures (creating if absent) the aggregate sub-database entry for
-- `iedName` and returns it: { ld=, points={[ref]=rec}, connOk=,
-- gooseState= (nil until the first GOOSE datagram from this IED
-- arrives; see sas.proto.goose.newSubscriberState) }.
function model.ensureIedEntry(aggDb, iedName)
  local entry = aggDb.ieds[iedName]
  if not entry then
    entry = { ld = nil, points = {}, connOk = false, gooseState = nil }
    aggDb.ieds[iedName] = entry
  end
  return entry
end

-- Ensures (creating if absent) a peer's GOOSE-only tracking entry: used
-- by an IED's own lightweight peer-point tracking for interlocking
-- (sas/ied/engine.lua's receiveGoosePeers/interlockBlocks). Deliberately
-- smaller than ensureIedEntry's aggregate-database entry -- no `ld` or
-- `connOk`, since an IED never opens an MMS connection to a peer IED, it
-- only ever hears its GOOSE. Returns { points = {[ref]=pointRec},
-- gooseState = nil } (gooseState set lazily on first received datagram
-- from that peer, same lazy-init pattern as ensureIedEntry's gooseState).
function model.ensureGoosePeerEntry(peersTbl, iedName)
  local entry = peersTbl[iedName]
  if not entry then
    entry = { points = {}, gooseState = nil }
    peersTbl[iedName] = entry
  end
  return entry
end

-- Replaces an IED entry's point set from a get-model-reply's point list
-- (each { ln, doName, type }, no live values yet).
function model.applyModelReply(aggDb, iedName, ld, points)
  local entry = model.ensureIedEntry(aggDb, iedName)
  entry.ld = ld
  entry.points = {}
  for _, p in ipairs(points) do
    local ref = model.ref(p.ln, p.doName)
    entry.points[ref] = {
      ln = p.ln, doName = p.doName, type = p.type,
      value = nil, quality = "invalid", lastChangeAt = nil,
    }
  end
  return entry
end

-- Updates a point record's live value/quality in place, returning true if
-- this call actually changed something (value, or quality transitioning
-- to/from "good"), so callers can decide whether to publish/report/log.
function model.setValue(pointRec, value, quality, t)
  quality = quality or "good"
  local changed = (pointRec.value ~= value) or (pointRec.quality ~= quality)
  pointRec.value = value
  pointRec.quality = quality
  if changed then
    pointRec.lastChangeAt = t
  end
  return changed
end

-- Iterates every point in an IED database (model.buildIedDatabase's
-- shape) or one IED entry of an aggregate database, calling
-- fn(ref, pointRec) for each.
function model.eachPoint(db, fn)
  for ref, rec in pairs(db.points) do
    fn(ref, rec)
  end
end

-- Iterates every point across every IED in an aggregate database, calling
-- fn(iedName, ref, pointRec) for each.
function model.eachAggregatePoint(aggDb, fn)
  for iedName, entry in pairs(aggDb.ieds) do
    for ref, rec in pairs(entry.points) do
      fn(iedName, ref, rec)
    end
  end
end

-- Looks up a point record in an aggregate database by its fully
-- qualified reference ("<iedName>/<ldName>/<LN>.<DOName>"). Returns the
-- point record, or nil if the IED/ref is unknown.
function model.lookupAggregatePoint(aggDb, fullRef)
  local iedName, _ldName, ln, doName = model.parseFullRef(fullRef)
  if not iedName then return nil end
  local entry = aggDb.ieds[iedName]
  if not entry then return nil end
  return entry.points[model.ref(ln, doName)]
end

return model
