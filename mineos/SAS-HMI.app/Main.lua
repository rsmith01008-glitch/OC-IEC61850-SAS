-- SAS HMI -- MineOS application entry point.
--
-- IMPORTANT, read before touching this file: the exact MineOS GUI/window-
-- manager/event-loop calls below (GUI.workspace(), GUI.panel(), GUI.button(),
-- workspace:start(), etc.) are written to the best-effort, publicly known
-- shape of MineOS's "GUI" library, but have NOT been verified against a
-- real MineOS install from this environment -- see the "MineOS risk" note
-- in README.md. Everything else in this file (the SCADA protocol client,
-- the SBO flow, the data model) reuses sas/proto/*, sas/model.lua and
-- sas/sbo.lua unchanged from the OpenOS-side SCADA/IED code, and does NOT
-- need to change even if the GUI calls do. If GUI.* calls turn out wrong,
-- fix them here and only here.
local GUI = require("GUI")
local event = require("event")

local config = require("sas.config")
local model = require("sas.model")
local mmsclient = require("sas.proto.mmsclient")

local CFG_PATH = "/etc/sas-hmi.cfg"
local DEFAULTS = {
  scada = { ip = "1.1", port = 8103 },
  operator = "operator1",
  pollIntervalSec = 0.5,
  mimicLayout = {},
}

local cfg = config.load(CFG_PATH, DEFAULTS)

--- Application state ------------------------------------------------------------

local app = {
  client = nil,           -- sas.proto.mmsclient.Client, once connected
  points = {},            -- [fullRef] = { ln, doName, type, value, quality, t, widget= }
  alarms = {},            -- array of alarm records (from the last alarm-update/alarm-list-reply)
  pending = {},            -- [fullRef] = { token=, expiresAt= } -- our own outstanding SBO selections
}

--- GUI construction ------------------------------------------------------------

local workspace = GUI.workspace()
local screenWidth, screenHeight = workspace.width, workspace.height

local mainContainer = workspace:addChild(GUI.container(1, 1, screenWidth, screenHeight))

local statusText = mainContainer:addChild(GUI.text(2, 1, 0xFFFFFF,
  "SAS HMI -- connecting to " .. cfg.scada.ip .. ":" .. cfg.scada.port .. " ..."))

local mimicPanel = mainContainer:addChild(GUI.container(2, 3, screenWidth - 2, screenHeight - 12))
local alarmPanel = mainContainer:addChild(GUI.container(2, screenHeight - 8, screenWidth - 2, 7))
local alarmTitle = alarmPanel:addChild(GUI.text(1, 1, 0xFFAA00, "Alarms"))
local alarmRows = {}

-- Colors matching each DPS state, per the plan's mimic-diagram spec.
local DPS_COLOR = {
  closed = 0x00CC00,
  open = 0xCC0000,
  intermediate = 0xCCCC00,
  bad = 0x888888,
}

local function qualityColor(quality, base)
  if quality == "stale" or quality == "invalid" then return 0x888888 end
  return base
end

--- Control dialog (select -> operate/cancel) ------------------------------------------------------------

local function closeDialogIfAny()
  if app.dialog then
    mainContainer:removeChild(app.dialog)
    app.dialog = nil
  end
end

local function sendControl(msgType, ref, extra, onReply)
  local req = { type = msgType, ref = ref, clientId = cfg.operator }
  if extra then for k, v in pairs(extra) do req[k] = v end end
  local id = app.client:sendRequest(req)
  app.awaitingReplies = app.awaitingReplies or {}
  if id then app.awaitingReplies[id] = onReply end
end

local function openControlDialog(fullRef, pointType)
  closeDialogIfAny()
  local w, h = 40, 9
  local x, y = math.floor((screenWidth - w) / 2), math.floor((screenHeight - h) / 2)
  local dialog = mainContainer:addChild(GUI.container(x, y, w, h))
  dialog:addChild(GUI.panel(1, 1, w, h, 0x1B1B1B))
  dialog:addChild(GUI.text(2, 1, 0xFFFFFF, "Control: " .. fullRef))
  local status = dialog:addChild(GUI.text(2, 3, 0xCCCCCC, "Not selected."))

  local selectBtn = dialog:addChild(GUI.button(2, 5, 14, 1, 0x333333, 0xFFFFFF, 0x666666, 0xFFFFFF, "Select"))
  local openBtn = dialog:addChild(GUI.button(2, 7, 14, 1, 0x006600, 0xFFFFFF, 0x00AA00, 0xFFFFFF, "Operate Open"))
  local closeBtn = dialog:addChild(GUI.button(18, 7, 14, 1, 0x660000, 0xFFFFFF, 0xAA0000, 0xFFFFFF, "Operate Close"))
  local cancelBtn = dialog:addChild(GUI.button(w - 12, 5, 10, 1, 0x333333, 0xFFFFFF, 0x666666, 0xFFFFFF, "Cancel"))
  openBtn.disabled, closeBtn.disabled = true, true

  selectBtn.onTouch = function()
    sendControl("select", fullRef, nil, function(reply)
      if reply.ok then
        app.pending[fullRef] = { token = reply.token }
        status.text = "Selected. Choose operate open/close, or cancel."
        openBtn.disabled, closeBtn.disabled = false, false
      else
        status.text = "Select failed: " .. tostring(reply.err)
      end
      workspace:draw()
    end)
  end

  local function operate(value)
    local sel = app.pending[fullRef]
    if not sel then return end
    sendControl("operate", fullRef, { token = sel.token, value = value }, function(reply)
      if reply.ok then
        status.text = "Operate " .. value .. " accepted."
        app.pending[fullRef] = nil
      else
        status.text = "Operate failed: " .. tostring(reply.err)
      end
      workspace:draw()
    end)
  end
  openBtn.onTouch = function() operate("open") end
  closeBtn.onTouch = function() operate("closed") end

  cancelBtn.onTouch = function()
    local sel = app.pending[fullRef]
    if sel then
      sendControl("cancel", fullRef, { token = sel.token }, function() end)
      app.pending[fullRef] = nil
    end
    closeDialogIfAny()
    workspace:draw()
  end

  app.dialog = dialog
  workspace:draw()
end

--- Mimic diagram ------------------------------------------------------------

local nextAutoX, nextAutoY = 1, 1
local AUTO_COLS = 4

local function layoutFor(fullRef)
  local manual = cfg.mimicLayout[fullRef]
  if manual then return manual.x, manual.y end
  local col = (nextAutoX % AUTO_COLS)
  local x, y = 1 + col * 18, 1 + nextAutoY * 2
  nextAutoX = nextAutoX + 1
  if nextAutoX % AUTO_COLS == 0 then nextAutoY = nextAutoY + 1 end
  return x, y
end

-- Rebuilds every mimic widget from scratch, called once after get-model.
local function buildMimic()
  mimicPanel:removeChildren()
  nextAutoX, nextAutoY = 0, 0
  for fullRef, p in pairs(app.points) do
    local x, y = layoutFor(fullRef)
    local label = p.ln .. "." .. p.doName
    if p.type == "DPS" or p.type == "SPS" then
      local widget = mimicPanel:addChild(GUI.button(x, y, 16, 1, 0x444444, 0xFFFFFF, 0x666666, 0xFFFFFF, label))
      p.widget = widget
      -- Only DPC/SPC control points open a control dialog; pure status
      -- points (no matching control counterpart) are display-only, but we
      -- don't distinguish that here for simplicity -- clicking a status-
      -- only point's tile just does nothing useful server-side (select
      -- on a non-control ref is rejected by the IED with a clear error).
      widget.onTouch = function() openControlDialog(fullRef, p.type) end
    elseif p.type == "MV" then
      local widget = mimicPanel:addChild(GUI.text(x, y, 0xFFFFFF, label .. ": --"))
      p.widget = widget
    end
    -- DPC/SPC control points themselves have no separate tile; they're
    -- reached via their paired status point's tile (same LN, e.g.
    -- XCBR1.Pos as both DPS status and DPC control -- see
    -- etc/sas-ied.cfg.example).
  end
end

local function refreshMimicWidget(fullRef)
  local p = app.points[fullRef]
  if not p or not p.widget then return end
  local label = p.ln .. "." .. p.doName
  if p.type == "DPS" then
    p.widget.colors.default.background = qualityColor(p.quality, DPS_COLOR[p.value] or 0x888888)
    p.widget.text = label .. ": " .. tostring(p.value)
  elseif p.type == "SPS" then
    p.widget.colors.default.background = qualityColor(p.quality, p.value and 0x00CC00 or 0x666666)
    p.widget.text = label .. ": " .. tostring(p.value)
  elseif p.type == "MV" then
    p.widget.text = label .. ": " .. tostring(p.value) .. (p.quality ~= "good" and (" [" .. p.quality .. "]") or "")
  end
end

--- Alarm panel ------------------------------------------------------------

local function refreshAlarmPanel()
  for _, row in ipairs(alarmRows) do alarmPanel:removeChild(row) end
  alarmRows = {}
  for i, a in ipairs(app.alarms) do
    if i > 5 then break end -- panel only shows the 5 most recent; full list belongs in a dedicated view
    local y = 2 + i
    local color = a.severity == "high" and 0xFF3333 or (a.severity == "medium" and 0xFFAA00 or 0xFFFF66)
    local label = string.format("[%s] %s%s", a.severity, a.message, a.acked and " (acked)" or "")
    local text = alarmPanel:addChild(GUI.text(1, y, color, label))
    table.insert(alarmRows, text)
    if not a.acked then
      local ackBtn = alarmPanel:addChild(GUI.button(screenWidth - 12, y, 10, 1, 0x333333, 0xFFFFFF, 0x666666, 0xFFFFFF, "Ack"))
      table.insert(alarmRows, ackBtn)
      ackBtn.onTouch = function()
        app.client:sendRequest({ type = "alarm-ack", alarmId = a.id, operator = cfg.operator })
      end
    end
  end
end

--- Network poll tick ------------------------------------------------------------

local function applyReport(values)
  for fullRef, v in pairs(values) do
    local p = app.points[fullRef]
    if p then
      p.value, p.quality, p.t = v.value, v.quality, v.t
      refreshMimicWidget(fullRef)
    end
  end
end

local function pollTick()
  if not app.client then return end
  local ok, err = app.client:poll()
  if not ok then
    statusText.text = "SAS HMI -- disconnected: " .. tostring(err)
    workspace:draw()
    return
  end

  for _, push in ipairs(app.client:drainInbox()) do
    if push.type == "report" then
      applyReport(push.values)
    elseif push.type == "alarm-update" then
      app.alarms = push.alarms
      refreshAlarmPanel()
    end
  end

  if app.awaitingReplies then
    for id, cb in pairs(app.awaitingReplies) do
      local reply = app.client:popReply(id)
      if reply then
        app.awaitingReplies[id] = nil
        cb(reply)
      end
    end
  end

  workspace:draw()
end

--- Startup ------------------------------------------------------------

local function connectAndLoadModel()
  local client, err = mmsclient.connect(cfg.scada.ip, cfg.scada.port, 10)
  if not client then
    statusText.text = "SAS HMI -- connect failed: " .. tostring(err)
    return
  end
  app.client = client
  statusText.text = "SAS HMI -- connected to " .. cfg.scada.ip .. ":" .. cfg.scada.port

  local modelReply, merr = client:request({ type = "get-model" }, 10)
  if not modelReply then
    statusText.text = "SAS HMI -- get-model failed: " .. tostring(merr)
    return
  end

  app.points = {}
  for _, p in ipairs(modelReply.points) do
    app.points[p.fullRef] = { ln = p.ln, doName = p.doName, type = p.type, value = nil, quality = "invalid" }
  end
  buildMimic()

  local subReply, serr = client:request({ type = "subscribe", refs = "*" }, 10)
  if not subReply then
    statusText.text = "SAS HMI -- subscribe failed: " .. tostring(serr)
  end

  local alarmReply = client:request({ type = "alarm-list" }, 10)
  if alarmReply then
    app.alarms = alarmReply.alarms
    refreshAlarmPanel()
  end
end

connectAndLoadModel()
workspace:draw()

-- Periodic poll, same event.timer pattern used by the OpenOS-side
-- iedd/scadad engines -- see sas/ied/engine.lua's file header for why
-- this is safe/correct under OpenComputers' cooperative event model.
event.timer(cfg.pollIntervalSec, pollTick, math.huge)

-- Hands control to MineOS's own event loop; it services event.timer
-- callbacks (including pollTick above) the same way OpenOS's shell does.
workspace:start(cfg.pollIntervalSec)
