# OC-IEC61850-SAS

An IEC 61850-inspired substation automation system for
[OpenComputers](https://oc.cil.li/): a generic **IED**, a **SCADA** data
concentrator, and a **MineOS** HMI, talking a simplified MMS-lite/GOOSE-lite
protocol over [OC-IP-Stack](https://github.com/rsmith01008-glitch/OC-IP-Stack)
(installed separately, unmodified, as an oppm dependency).

This is not a byte-perfect implementation of the real IEC 61850 standard --
no SCL/ACSI object model, no real MMS/GOOSE wire encoding. It borrows
61850's logical-device/logical-node/data-object naming, its
client/server-reporting + GOOSE peer-messaging + select-before-operate
control model, and applies them at a scope appropriate for an
OpenComputers-scale network -- matching OC-IP-Stack's own "don't
over-engineer for OC scale" design philosophy. GOOSE rides OC-IP-Stack's
real multicast primitive (`ipstack.socket.multicast()`): subnet 255
(`ip.MULTICAST_SUBNET`) is reserved for multicast group addresses in the
same `"subnet.host"` space as everything else; there's no IGMP-equivalent
(join/leave are purely local/software, never go on the wire); and,
notably for a substation-scale deployment with relay nodes, a multicast
group never crosses a relay node's other interfaces even with
`ip.forwarding = true` -- it stays within its originating broadcast
domain, matching real GOOSE's non-routed nature. MMS-lite (everything
else -- get-model/read/subscribe/report/select/operate/cancel/alarm/
history) stays TCP/unicast, matching the real standard, since MMS is
never multicast in actual IEC 61850 either.

## Architecture

```
   HMI (MineOS)  <--MMS-lite (TCP)-->  SCADA  <--MMS-lite (TCP)-->  IED A
                                         |                            |
                                         +====== GOOSE-lite ==========+==== IED B  ...
                                          (multicast, one shared       |
                                           group; SCADA subscribes    ...
                                           only, IEDs pub+sub)
```

One shared GOOSE multicast group per station (`goose.group`, same address
configured on the SCADA and on every IED): SCADA only subscribes; every
IED both publishes its own points and subscribes to every other IED's, so
peer-to-peer interlocking (see below) needs no involvement from SCADA.

- **IED** (`sas/ied/engine.lua`, `rc.d/iedd.lua`): one generic,
  config-driven program. Behavior is entirely defined by
  `/etc/sas-ied.cfg` -- logical device name, and a list of logical-node
  data-object points (breaker/switch status & control via redstone,
  analog measurements via Create: Electro-Energistics meter blocks). Same
  program image runs on every IED; only the config differs. Also
  subscribes to the shared GOOSE multicast group to track peer-published
  points, for locally evaluated `interlocks` (see below) -- not just to
  publish its own.
- **SCADA** (`sas/scada/engine.lua`, `rc.d/scadad.lua`): connects out to
  every configured IED (learns each one's point list automatically via a
  `get-model` request -- no hand-duplicated point lists in
  `sas-scada.cfg`), subscribes to reports and GOOSE, maintains a live
  aggregate database, evaluates alarms, logs to a historian, and serves
  that aggregate to HMI clients. Forwards HMI control commands down to the
  owning IED; SCADA itself holds no select-before-operate reservation
  state of its own (see `sas/sbo.lua`).
- **HMI** (`mineos/SAS-HMI.app/`): a MineOS GUI application, not an
  OpenOS/oppm package. Pure MMS-lite client of SCADA -- never talks to an
  IED directly.

Both `iedd` and `scadad` are `rc.d` daemons whose tick callback
(`event.timer`) does one **entirely non-blocking** sweep every cycle --
this mirrors OC-IP-Stack's own `ipstackd`/`daemon.lua` skeleton exactly,
rather than inventing a different concurrency model. This relies on two
facts confirmed by reading OC-IP-Stack's actual source, not assumed:
`ipstack.socket` calls passed an explicit `timeoutSec = 0` (or, for
`listener:accept()`, no argument at all) check their underlying condition
exactly once and return immediately rather than yielding
(`ipstack/core.lua`'s `waitUntil`); and `event.timer`/`event.listen`
callbacks are serviced by *any* coroutine's `pullSignal`, not just the one
that registered them (`ipstack/daemon.lua`).

## Install (OpenOS: SCADA and IED nodes)

```
oppm install oc-ip-stack
cp /etc/ipstack.cfg.example /etc/ipstack.cfg   # edit: assign this node's modem(s) an address
rc ipstackd enable
rc ipstackd start

oppm install oc-sas-ied      # on an IED node
cp /etc/sas-ied.cfg.example /etc/sas-ied.cfg   # edit: logical device, points, I/O bindings
rc iedd enable
rc iedd start

oppm install oc-sas-scada    # on the SCADA node
cp /etc/sas-scada.cfg.example /etc/sas-scada.cfg   # edit: configured IEDs, alarms, historian
rc scadad enable
rc scadad start
```

Inspect a running `iedd`/`scadad` with `sas-ctl <status|points|alarms|log [n]>`
(mirrors OC-IP-Stack's own `ipstack-ctl`).

## Install (MineOS: HMI node)

Copy `mineos/SAS-HMI.app/` into MineOS's Applications folder on the HMI
machine, and `sas/`, `sas/proto/`, `sas/sbo.lua`, `sas/model.lua`,
`sas/config.lua`, `sas/util.lua` alongside it somewhere MineOS's `require()`
can resolve (oppm can't install into a MineOS filesystem, so this is a
manual copy, not `oppm install`). Copy `etc/sas-hmi.cfg.example` to
`/etc/sas-hmi.cfg` and edit it (SCADA address/port, operator name).

**Known risk:** whether OC-IP-Stack's `ipstackd`/`require("ipstack.socket")`
runs cleanly under MineOS (a distinct OS from OpenOS, with its own
filesystem/event/window-manager implementation) is unverified from this
development environment. Per direction, the HMI is built assuming it works
the same way it does under OpenOS/SCADA; verify this on first real
deployment. If it does not port cleanly, the fallback is a small headless
OpenOS "gateway" machine running `ipstackd` + a thin bridge, networked to
the MineOS machine, so the HMI's `sas/proto/mmsclient.lua` and
`sas/model.lua` code needs no changes -- only the transport glue moves.
Likewise, `mineos/SAS-HMI.app/Main.lua`'s `GUI.*`/`workspace:*` calls are
written to the best-effort publicly documented shape of MineOS's `GUI`
library and should be confirmed/adjusted against a real MineOS install
before relying on this HMI.

## Protocol summary

See `sas/proto/messages.lua` for the full message catalog (`get-model`,
`read`, `subscribe`/`report`, `select`/`operate`/`cancel`, `alarm-list`/
`alarm-ack`, `history-query`, `heartbeat`). TCP messages are length-prefixed
(`sas/proto/framing.lua`). GOOSE (`sas/proto/goose.lua`) is multicast
(`ipstack.socket.multicast()`), one shared group per station (`goose.group`
in both `sas-ied.cfg` and `sas-scada.cfg`, default `"255.10"`), still
carrying the same `stNum`/`sqNum` change/retransmit-burst-then-heartbeat
model. Every IED both publishes and subscribes (for peer interlocking,
below); SCADA only subscribes.

## Peer interlocking

Real IEC 61850 GOOSE's primary use case is direct peer-to-peer IED
interlocking -- e.g. a breaker refusing to close while a neighboring IED's
breaker reports closed -- entirely independent of SCADA. A config-driven
`interlocks` list in `sas-ied.cfg` (see `etc/sas-ied.cfg.example`) defines
rules of the form "block operating `localRef` to `blockValue` while
`peerIed`'s GOOSE-sourced `peerRef` satisfies `condition`/`peerValue`".
Rules are evaluated on the controlling IED itself (`sas/ied/engine.lua`'s
`handleOperate`), after select-before-operate validation succeeds but
before the physical output is applied -- only `operate` carries the
target value, so `select` is never interlock-checked. **Fail-safe by
default:** if the referenced peer point has never been heard, or its
GOOSE has gone stale (`gooseStaleAfterSec`), the operate is blocked; a
rule can opt into `failOpen = true` when availability matters more than
that specific safety case. Interlock rules are validated at `iedd` startup
(`sas/ied/engine.lua`'s `validateInterlocks`) -- a misconfigured rule
refuses to start the daemon rather than silently no-op. SCADA is entirely
uninvolved in interlocking (it only relays `operate` to the owning IED,
same as before).

## Known limitations / risks

- **Create: Electro-Energistics meter method names** (`sas/io/meter.lua`,
  `io.method` in `sas-ied.cfg`) are placeholders (`getVoltage`/
  `getCurrent`) -- confirm the real OC component method names in-game
  (e.g. `component.proxy(addr).getMethods()`) before relying on analog
  readings.
- **MineOS GUI API and OC-IP-Stack-under-MineOS compatibility** -- see
  above.
- Everything else (protocol, data model, control flow, redstone I/O) was
  validated by direct code review against OC-IP-Stack's actual source, not
  its README alone, but none of it has been run inside the actual mod --
  see Testing below.

## Testing

There is no way to execute `component`/`event`/OpenComputers or MineOS APIs
outside the actual game (the same limitation OC-IP-Stack's own README
documents). Every file was syntax-checked with `luac5.3 -p` (Lua 5.3,
matching OpenComputers' Lua version); `.luacheckrc` declares the OC/OpenOS
globals this codebase uses.

Manual/in-game (or [OCEmu](https://github.com/zenith391/OCEmu)) test
runbook, in order:

1. **Bring-up + model discovery.** Two OpenOS machines with `ipstackd`
   running; `iedd` on node A (one `XCBR` bound to redstone, one `MMXU`
   bound to a Create:EE meter); `scadad` on node B pointed at A via
   `sas-scada.cfg`. `sas-ctl status`/`sas-ctl points` on B should show A's
   full point list without it being hand-configured in `sas-scada.cfg`.
2. **Status change -> GOOSE -> aggregate -> historian.** Toggle the
   redstone input feeding `XCBR1.Pos`. Confirm a GOOSE datagram fires
   within the first `burstIntervalsSec` entry, `sas-ctl points` on B
   reflects the new value, and a line is appended under
   `historian.dir` on B. GOOSE now needs zero per-IED peer configuration
   on SCADA beyond `goose.group` matching every IED's -- confirm SCADA
   receives A's GOOSE purely by having joined the same group, with no
   `sas-scada.cfg` entry naming A as a GOOSE source.
3. **MV deadband behavior.** Drive the bound meter's value past
   `deadband`; confirm a report/GOOSE fires. Wiggle it by less than
   `deadband`; confirm no report/GOOSE fires, but the value still
   eventually converges via the IED's `integritySec` refresh.
4. **Select-before-operate.** From a third test client (or the HMI once
   built): `select` a control point, confirm a second `select` from a
   different `clientId` is rejected while the first is outstanding;
   `operate` and confirm the correct redstone side pulses for
   `pulseMs`; confirm an un-operated reservation auto-expires
   (`sbo.timeoutSec`) and becomes selectable again.
5. **Peer interlock.** Two IED nodes (A = `IED-BRK1`, B = `IED-BRK2`),
   both joined to the same `goose.group`, each publishing its own
   `XCBR1.Pos` as GOOSE, with A configured with an `interlocks` rule
   blocking `XCBR1.Pos = "closed"` while B's `XCBR1.Pos` GOOSE-sourced
   value equals `"closed"`. Drive B's `XCBR1.Pos` to `"closed"` (real
   redstone input); `select`+`operate` A's `XCBR1.Pos` to `"closed"` and
   confirm the `operate-reply` comes back `ok=false` with the interlock's
   blocking reason, and A's physical output is not pulsed. Change B's
   value away from `"closed"` and confirm the same operate now succeeds.
   Then stop B's `iedd` entirely so its GOOSE goes stale past
   `gooseStaleAfterSec`, confirm A's operate is still blocked (default
   fail-safe), set `failOpen = true` on the rule, and confirm it is now
   allowed through (fail-open verified).
6. **Alarms.** Configure an `sas-scada.cfg` alarm condition; confirm it
   appears via `sas-ctl alarms`/`alarm-list`, ack it via `alarm-ack`,
   confirm it clears when the condition resolves, and confirm a
   not-yet-acked alarm that clears stays visible until acked.
7. **Comm loss/recovery.** Stop `ipstackd` (or unplug the modem) on IED A.
   Confirm SCADA raises a `COMM_<iedName>` alarm (TCP loss) and, after
   `gooseStaleAfterSec`, a `GOOSE_<iedName>` alarm. Restart; confirm
   reconnect, `get-model` + `subscribe` re-run, and a full resync --
   without manually restarting `scadad`.
8. **HMI.** Before GUI polish: confirm `require("ipstack.socket")` and a
   `select`/`operate` round trip work from a minimal script under real
   MineOS (the risk noted above). Then exercise the mimic diagram,
   control dialog, alarm panel/ack, and history query end to end.
