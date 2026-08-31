-- /etc/rc.d/scadad.lua -- OpenOS rc.d service wrapper for the SAS SCADA
-- data-concentrator daemon. Mirrors OC-IP-Stack's own rc.d/ipstackd.lua.
-- All real work lives in sas.scada.engine (a library module, so it can
-- also be required directly by usr/bin/sas-ctl.lua).
local engine = require("sas.scada.engine")

function start()
  return engine.start()
end

function stop()
  return engine.stop()
end

function status()
  if engine.isRunning() then
    local n = 0
    for _ in pairs(engine.state.iedClients) do n = n + 1 end
    print("scadad: running (" .. n .. " configured IED(s))")
  else
    print("scadad: stopped")
  end
end
