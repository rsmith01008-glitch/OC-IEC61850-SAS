-- /etc/rc.d/iedd.lua -- OpenOS rc.d service wrapper for the generic
-- IEC 61850-style IED daemon. Mirrors OC-IP-Stack's own
-- rc.d/ipstackd.lua: `rc` invokes start()/stop()/status() synchronously
-- in the caller's own process; `restart` is provided for free by `rc` as
-- stop()+start(). All real work lives in sas.ied.engine (a library module,
-- so it can also be required directly by usr/bin/sas-ctl.lua).
local engine = require("sas.ied.engine")

function start()
  return engine.start()
end

function stop()
  return engine.stop()
end

function status()
  if engine.isRunning() then
    print("iedd: running (" .. tostring(engine.state.iedName) .. "/" .. tostring(engine.state.cfg and engine.state.cfg.logicalDevice) .. ")")
  else
    print("iedd: stopped")
  end
end
