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
  scl/switchyard.scd  --[offline SCL compiler]-->  etc/generated/*.cfg  --[manual copy]-->  /etc/sas-*.cfg

   HMI (MineOS)  <--MMS-lite (TCP)-->  SCADA  <--MMS-lite (TCP)-->  IED A
                                         |                            |
                                         +====== GOOSE-lite ==========+==== IED B  ...
                                          (multicast, one shared       |
                                           group; SCADA subscribes    ...
                                           only, IEDs pub+sub)
```

Before any of the runtime pieces below start, there's a build-time stage:
`scl/switchyard.scd` (an IEC 61850-6 SCL document -- the single source of
truth for switchyard topology, communication, protection, and reporting
config) is compiled offline into the `sas-ied-<name>.cfg`/`sas-scada.cfg`
files the runtime actually reads. See "SCL / Substation Configuration
Language" below.

One shared GOOSE multicast group per station (`goose.group`, same address
configured on the SCADA and on every IED): SCADA only subscribes; every
IED both publishes its own points and subscribes to every other IED's, so
peer-to-peer interlocking (see below) needs no involvement from SCADA.

- **IED** (`sas/ied/engine.lua`, `rc.d/iedd.lua`): one generic,
  config-driven program. Behavior is entirely defined by
  `/etc/sas-ied.cfg` -- logical device name, and a list of logical-node
  data-object points (breaker/switch status & control via redstone,
  analog measurements via Create: Electro-Energistics meter blocks, each
  reached through an OpenComputers Adapter block since the mod only
  exposes a ComputerCraft peripheral -- see `sas/io/meter.lua`). Same
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

## SCL / Substation Configuration Language

Switchyard topology, GOOSE/report communication, and protection settings
are authored once as real IEC 61850-6 SCL (`scl/switchyard.scd`), not
hand-duplicated across `.cfg` files. An offline compiler
(`tools/scl-compiler/`, Python 3 + `lxml` -- does **not** run on OC
hardware) maps it onto this project's existing Lua-table-literal config
format:

```
python3 tools/scl-compiler/scl_compile.py \
  --scd scl/switchyard.scd --out-dir etc/generated/ --validate-xsd
```

The generated `etc/generated/sas-ied-<name>.cfg`/`sas-scada.cfg` files are
checked into this repo as a golden reference (`--check` diffs freshly
compiled output against them, for CI); a deployer copies the one matching
each in-game OC computer to `/etc/sas-ied.cfg`/`/etc/sas-scada.cfg` --
that last copy step stays manual since OC computers don't run Python.
`etc/sas-ied.cfg.example`/`etc/sas-scada.cfg.example` remain separately
hand-maintained as the lowest-barrier single-IED quickstart (unrelated to
the compiler, not generated).

Real SCL never encodes protection/interlock/synchrocheck algorithms --
only LN instances and their settable parameters. Everything this codebase
needs that has no standard SCL home (redstone/meter I/O bindings, SBO
timeouts, interlock/remote-trip rules, protection scheme parameters,
GOOSE transport addressing, report cadence, SCADA's historian/alarms)
lives in `Private type="oc-iec61850-sas"` extensions
(`xmlns:oc="urn:oc-iec61850-sas:v1"`) -- see `tools/scl-compiler/README.md`
and `scl/README.md` for the exact element shapes and what the compiler
does/doesn't consume. In particular: `GSE/Address` MAC-Address/APPID/
VLAN-ID/VLAN-PRIORITY and `SampledValueControl`/`SMV` are carried as
schema-real but purely **descriptive** metadata -- OC-IP-Stack has no
802.1Q/priority-queue or process-bus-streaming transport underneath, so
none of it is enforced (a possible future OC-IP-Stack enhancement, not
part of this repo).

`scl/switchyard.scd` is a minimal, hand-verifiable worked example: a
1½-breaker 800kV/230kV switchyard (two 3-breaker diameters, one
transformer, one line, one feeder -- see `scl/README.md` for the full
topology and why it's trivially repeatable for a larger station).

## Protection

`sas/protection/{curves,ptoc,pdif,pdis}.lua`, evaluated every `iedd` tick
(`sas/ied/engine.lua`'s `evaluateProtection`), configured via
`sas-ied.cfg`'s `protection` section (see `etc/sas-ied.cfg.example`).
Protection trips **bypass select-before-operate entirely** and call the
physical output directly -- matching real substation practice (protection
is direct-with-normal-security, never SBO; SBO exists to guard *human*
commands, not time-critical automatic ones) -- and, by default, bypass
`interlocks` too (`respectInterlocks = false`, overridable per scheme:
"protection wins"). A trip **latches**: once tripped, a scheme stops
re-evaluating and won't re-pulse the breaker until `iedd` restarts. Every
protection scheme auto-registers a synthetic `<name>.Op` status point
(always GOOSE-published), independent of any SCL `DataSet` -- this is how
a **remote trip** command reaches a breaker the protection scheme doesn't
own (see `remoteTrips` in `etc/sas-ied.cfg.example` -- structurally the
inverse of `interlocks`: forces an operate instead of blocking one).

- **PTOC** (time-overcurrent, `sas/protection/ptoc.lua`): real trip logic.
  `sas/protection/curves.lua` implements the standard IEC 60255-151/IEEE
  C37.112 inverse-time curve formulas plus `DEFINITE_TIME`; a
  percentage-operate-time accumulator generalizes a curve's constant-
  current trip time to fluctuating load (`accum += dt/timeToTrip(M,tms)`
  while over pickup, decaying by `resetSec` otherwise). Magnitude-only,
  same as every measurement in this codebase (Create:EE's `getValue()`
  has no phase angle) -- a plain overcurrent scheme only ever needs
  magnitude anyway, so this is a real, working relay.
- **PDIF** (transformer differential, `sas/protection/pdif.lua`): real
  trip logic, magnitude-restrained (no vector/phase-shift compensation).
  Requires two local CT inputs (HV+LV) on the *same* IED -- there's no
  low-latency cross-IED read path suitable for a differential trip's
  timing, which is why a transformer needs its own dedicated protection
  IED with local HV+LV meters (see `scl/README.md`'s `XFMR1`) rather than
  living on a breaker IED.
- **PDIS** (distance, `sas/protection/pdis.lua`): **not functional.**
  Impedance is a V/I phasor ratio, and this hardware has no phase-angle
  data source -- only scalar magnitude. Config-modeled for data-model
  completeness (`zone1/2ReachOhms`/`DelaySec` settings carry through to
  the compiled `.cfg`); the module logs "NOT FUNCTIONAL" once at `iedd`
  startup and registers a dead `Op` point so SCADA/HMI show the tag
  rather than a missing reference, instead of silently doing nothing.

## Reporting

`ReportControl`/`DataSet`/`TrgOps` (real SCL) map to a `reports` section
in `sas-ied.cfg` -- a dataset + trigger-option-gated filter layered on top
of (not replacing) the existing tick-driven poll loop. SCADA
auto-subscribes to the first report an IED advertises; an IED with no
`reports` configured (e.g. a hand-written `sas-ied.cfg` not yet SCL-ified)
keeps today's unconditional "everything, every tick" behavior unchanged.
`trgOps.dchg`/`qchg` gate on real change; `period` (needs a companion
`periodSec`, since real SCL's `TrgOps/period` is a boolean with no
interval) reports on a cadence regardless of change; `gi` sends one full
dataset immediately on (re)subscribe; `bufTime` enforces a minimum
re-report interval, IED-side. Deadband stays orthogonal (independent
per-point suppression, unrelated to trigger options).

## Install (OpenOS: SCADA and IED nodes)

Optional, once (on a real computer, not in-game -- see "SCL /
Substation Configuration Language" above): compile `scl/switchyard.scd`
(or your own) and copy the matching generated file over the hand-edited
`.cfg` step below.

```
pip3 install -r tools/scl-compiler/requirements.txt
python3 tools/scl-compiler/scl_compile.py \
  --scd scl/switchyard.scd --out-dir etc/generated/ --validate-xsd
# then copy etc/generated/sas-ied-<name>.cfg / sas-scada.cfg onto each
# node as /etc/sas-ied.cfg / /etc/sas-scada.cfg, instead of the
# cp .../*.cfg.example step below.
```

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

Copy `mineos/SAS-HMI.app/` into MineOS's `Applications` folder on the HMI
machine (per MineOS's own docs, an application is just a `.app` directory
containing `Main.lua` plus an optional `Icon.pic` -- see
`mineos/SAS-HMI.app/ICON_NOTE.txt`), and `sas/`, `sas/proto/`,
`sas/sbo.lua`, `sas/model.lua`, `sas/config.lua`, `sas/util.lua` alongside
it somewhere MineOS's `require()` can resolve (oppm can't install into a
MineOS filesystem, so this is a manual copy, not `oppm install`). Copy
`etc/sas-hmi.cfg.example` to `/etc/sas-hmi.cfg` and edit it (SCADA
address/port, operator name).

`mineos/SAS-HMI.app/Main.lua`'s `GUI.*`/`system.*`/`event.*` calls
(`system.addWindow`, `GUI.titledWindow`, `GUI.addBackgroundContainer`,
`event.addHandler`, `object:remove()`, etc.) have been cross-checked
against MineOS's actual wiki
(`github.com/IgorTimofeev/MineOS.wiki`, `System-API.md`/`GUI-API.md`/
`Event-API.md`) -- not guessed, as an earlier version of this file was.
That verification also caught and fixed a bug that would have broken the
app outright: creating a second top-level `GUI.workspace()` and calling
`workspace:start()` conflicts with MineOS's own already-running desktop
event loop; the app now adds a window into MineOS's existing shared
workspace (`system.addWindow`) and registers its network-poll callback via
MineOS's own `event.addHandler`, matching the pattern in `System-API.md`'s
own MineOS-integration example. Two details remain genuinely unverified
since the wiki doesn't document them: `Icon.pic`'s exact pixel
format/dimensions, and the title bar's exact height in rows (`Main.lua`'s
`TITLE_HEIGHT` is an approximation) -- both cosmetic, not structural.

**Known risk:** whether OC-IP-Stack's `ipstackd`/`require("ipstack.socket")`
runs cleanly under MineOS (a distinct OS from OpenOS, with its own
filesystem/kernel implementation) is unverified from this development
environment -- this is a transport-layer question, unrelated to the GUI
API points above. Per direction, the HMI is built assuming it works the
same way it does under OpenOS/SCADA; verify this on first real deployment.
If it does not port cleanly, the fallback is a small headless OpenOS
"gateway" machine running `ipstackd` + a thin bridge, networked to the
MineOS machine, so the HMI's `sas/proto/mmsclient.lua` and `sas/model.lua`
code needs no changes -- only the transport glue moves.

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

- **Create: Electro-Energistics meter binding** (`sas/io/meter.lua`,
  `sas-ied.cfg`'s `MMXU1.Vol`/`MMXU1.Amp` points) is no longer a
  placeholder guess -- verified against the mod's actual source (single
  shared `getValue()` method, quantity determined by the physical block)
  and against OpenComputers' own Adapter bridge source (an Adapter block
  is required, since the mod only exposes a ComputerCraft peripheral).
  See `sas/io/meter.lua`'s header for the full citation. Residual risk:
  verified against source, not by running it in-game -- spot-check
  `component.list()`/`component.proxy(addr).getMethods()` against your
  actual modpack's OpenComputers build, and set each gauge's in-world
  scale dial to match the configured `deadband`.
- **`ipstackd`-under-MineOS compatibility** and two cosmetic MineOS
  details (`Icon.pic` format, exact title bar height) -- see above. The
  MineOS GUI API calls themselves are no longer a guess (cross-checked
  against MineOS's actual wiki), only whether they've been run against a
  real MineOS install (see Testing below).
- Everything else (protocol, data model, control flow, redstone I/O) was
  validated by direct code review against OC-IP-Stack's actual source, not
  its README alone, but none of it has been run inside the actual mod --
  see Testing below.
- **PDIS (distance protection) is not functional** -- config-modeled only.
  See "Protection" above for why (no phase-angle data source).
- **GOOSE VLAN/priority/MAC/APPID and Sampled Values are descriptive-only**
  in the SCL/compiler and carry no enforcement -- OC-IP-Stack has no
  802.1Q/priority-queue concept or process-bus streaming transport
  underneath `ipstack.socket.multicast()`. See "SCL / Substation
  Configuration Language" above.
- **One `LDevice` per IED, compiler-enforced.** `tools/scl-compiler/`
  refuses to compile an `IED` with more or fewer than exactly one
  `LDevice` -- matches `sas/model.lua`'s hardcoded single-logical-device-
  per-IED assumption, not a real 61850 constraint.
- **Synchrocheck (`RSYN`) is not modeled at all**, not even inertly --
  same hardware limitation as PDIS (no phase-angle data), and unlike
  PDIS there's no settings-only value in carrying it through since a
  synchrocheck's entire job is comparing phase across an open breaker.

## Testing

There is no way to execute `component`/`event`/OpenComputers or MineOS APIs
outside the actual game (the same limitation OC-IP-Stack's own README
documents). Every file was syntax-checked with `luac5.3 -p` (Lua 5.3,
matching OpenComputers' Lua version); `.luacheckrc` declares the OC/OpenOS
globals this codebase uses. `sas/protection/{curves,ptoc,pdif}.lua` have
zero OC-API coupling (no `component`/`event`) and are genuinely
unit-tested via plain `lua5.3 tests/protection/test_*.lua` against
published IEC/IEEE reference values, not just syntax-checked.
`tools/scl-compiler/` (Python, runs outside the game entirely) has its
own `python3 -m unittest discover -s tools/scl-compiler/tests` suite plus
a golden-file round-trip check (`scl_compile.py --check`) -- see that
tool's README.

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
   `XCBR1.Pos` status as GOOSE, with A configured with an `interlocks`
   rule blocking `XCBR1.PosCtl = "closed"` (the control point -- not the
   status point of the same name, see `sas-ied.cfg.example`'s
   `XCBR1.Pos`/`XCBR1.PosCtl` pair) while B's `XCBR1.Pos` GOOSE-sourced
   status value equals `"closed"`. Drive B's `XCBR1.Pos` to `"closed"`
   (real redstone input); `select`+`operate` A's `XCBR1.PosCtl` to
   `"closed"` and confirm the `operate-reply` comes back `ok=false` with
   the interlock's blocking reason, and A's physical output is not
   pulsed. Change B's value away from `"closed"` and confirm the same
   operate now succeeds.
   Then stop B's `iedd` entirely so its GOOSE goes stale past
   `gooseStaleAfterSec`, confirm A's operate is still blocked (default
   fail-safe), set `failOpen = true` on the rule, and confirm it is now
   allowed through (fail-open verified).
6. **PTOC trip.** Configure a `protection.ptoc` scheme on an IED (see
   `etc/sas-ied.cfg.example`); drive the bound ammeter above `pickup` and
   hold it there. Confirm `<name>.Op` goes true once the accumulator
   crosses 1.0 (roughly `curves.timeToTrip(curve, measured/pickup, tms)`
   seconds after crossing pickup, not instantly), the breaker's control
   point pulses **without** a `select` ever happening (protection bypasses
   SBO), and a second overcurrent excursion after the trip does *not*
   re-pulse it (latched until `iedd` restart). Drive the current back
   under pickup before tripping and confirm the accumulator decays
   (`resetSec`) instead of tripping.
7. **PDIF trip + remote trip.** Three IED nodes: a transformer-protection
   IED with local HV+LV CT meters and a `protection.pdif` scheme, plus two
   breaker IEDs each carrying a `remoteTrips` rule watching that scheme's
   `PDIF1.Op`. Drive the two CT readings apart past `minPickup`/
   `restraintSlope` (e.g. hold LV near zero while HV carries load, an
   "internal fault" pattern) and confirm `PDIF1.Op` goes true, both
   breaker IEDs' control points pulse to `open` within one GOOSE
   burst-retransmit interval, and a balanced/through-load current pair
   does *not* trip it.
8. **ReportControl.** Configure `reports` on an IED (see `rcbStatus1` in
   `etc/sas-ied.cfg.example`); confirm SCADA's `subscribe` names the
   `rcbName` (not `refs="*"`) and receives one full-dataset report
   immediately (`gi`). Change a dataset point; confirm a report fires per
   `trgOps.dchg`/`qchg`. Set `bufTime > 0` and confirm rapid successive
   changes are coalesced to at most one report per `bufTime`. An IED with
   no `reports` configured should keep receiving the old unconditional
   `refs="*"` subscribe, unaffected.
9. **Alarms.** Configure an `sas-scada.cfg` alarm condition; confirm it
   appears via `sas-ctl alarms`/`alarm-list`, ack it via `alarm-ack`,
   confirm it clears when the condition resolves, and confirm a
   not-yet-acked alarm that clears stays visible until acked.
10. **Comm loss/recovery.** Stop `ipstackd` (or unplug the modem) on IED A.
   Confirm SCADA raises a `COMM_<iedName>` alarm (TCP loss) and, after
   `gooseStaleAfterSec`, a `GOOSE_<iedName>` alarm. Restart; confirm
   reconnect, `get-model` + `subscribe` re-run, and a full resync --
   without manually restarting `scadad`.
11. **HMI.** Before GUI polish: confirm `require("ipstack.socket")` and a
   `select`/`operate` round trip work from a minimal script under real
   MineOS (the risk noted above). Then exercise the mimic diagram,
   control dialog, alarm panel/ack, and history query end to end.
