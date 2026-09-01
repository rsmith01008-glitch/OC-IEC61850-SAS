"""Parsing for this project's `Private type="oc-iec61850-sas"` extension
elements -- the OC-specific detail real SCL has no standard home for
(redstone/meter I/O bindings, SBO timeouts, deadbands, tick intervals,
interlock/remote-trip rules, GOOSE transport addressing, report cadence).

Every element/attribute name here is OURS (defined by this project, not
IEC), so there is no schema to cross-check against -- only internal
consistency with etc/sas-ied.cfg.example's field names, which these
functions build dicts shaped exactly like.

Type coercion is deliberately explicit per attribute (`_attrs(elem, keys,
numeric=...)`), NOT guessed from content -- a blind "looks like a number ->
float" rule silently corrupts values like a gooseGroup/mmsAddress
"255.10"/"1.10" (an OC-IP-Stack subnet.host string, not a decimal) into
255.1/1.1.
"""

from .parse import oc_q, find_private


def _coerce_numeric(value):
    """int if it parses as one, else float, else the raw string (for the
    rare field -- alarm `value` -- that's genuinely number-or-string).
    """
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def _coerce_bool_or_str(value):
    low = value.strip().lower()
    if low in ("true", "false"):
        return low == "true"
    return value


def _attrs(elem, keys, numeric=frozenset()):
    """Pull just `keys` off `elem`'s attributes, omitting any not present.
    Keys in `numeric` are parsed as int/float; everything else is
    bool-or-string ("true"/"false" -> Python bool, else left as-is --
    strings like "255.10" or "closed" are never number-guessed).
    """
    out = {}
    for k in keys:
        v = elem.get(k)
        if v is None:
            continue
        out[k] = _coerce_numeric(v) if k in numeric else _coerce_bool_or_str(v)
    return out


_REDSTONE_NUMERIC = frozenset({
    "openSide", "closedSide", "side", "onLevel", "tripSide", "closeSide",
    "pulseMs", "sboTimeoutSec",
})
_IED_SETTINGS_NUMERIC = frozenset({
    "tickIntervalSec", "integritySec", "gooseStaleAfterSec", "mmsPort",
    "hmsPort", "resyncSec", "connectTimeoutSec", "reconnectIntervalSec",
})
_INTERLOCK_NUMERIC = frozenset({"staleAfterSec"})
_PTOC_NUMERIC = frozenset({
    "pickup", "timeMultiplier", "definiteTimeSec", "resetSec",
})
_PDIF_NUMERIC = frozenset({"minPickup", "restraintSlope"})
_PDIF_INPUT_NUMERIC = frozenset({"scale"})
_PDIS_NUMERIC = frozenset({
    "zone1ReachOhms", "zone1DelaySec", "zone2ReachOhms", "zone2DelaySec",
})
_TRANSPORT_NUMERIC = frozenset({"gooseGroupPort"})
_REPORT_SETTINGS_NUMERIC = frozenset({"periodSec"})
_HISTORIAN_NUMERIC = frozenset({"maxBytes", "maxFiles"})


def point_private(doi_elem):
    """DOI/Private/oc:point -> {io={...}, sbo={...}, deadband=...} or {} if absent.

    <oc:point deadband="0.5">
      <oc:redstoneIo openSide="0" closedSide="1"/>  -- DPS
      <!-- or -->
      <oc:redstoneIo tripSide="2" closeSide="3" pulseMs="250" sboTimeoutSec="30"/>  -- DPC
      <!-- or -->
      <oc:redstoneIo side="4" onLevel="1"/>  -- SPS
      <!-- or -->
      <oc:meterIo address="..." method="getValue"/>  -- MV
    </oc:point>
    """
    priv = find_private(doi_elem)
    if priv is None:
        return {}
    point_elem = priv.find(oc_q("point"))
    if point_elem is None:
        return {}

    out = {}
    deadband = point_elem.get("deadband")
    if deadband is not None:
        out["deadband"] = _coerce_numeric(deadband)

    redstone = point_elem.find(oc_q("redstoneIo"))
    meter = point_elem.find(oc_q("meterIo"))
    if redstone is not None:
        io = {"kind": "redstone"}
        io.update(_attrs(redstone, [
            "address", "openSide", "closedSide", "side", "onLevel",
            "tripSide", "closeSide", "pulseMs",
        ], numeric=_REDSTONE_NUMERIC))
        out["io"] = io
        sbo_timeout = redstone.get("sboTimeoutSec")
        if sbo_timeout is not None:
            out["sbo"] = {"timeoutSec": _coerce_numeric(sbo_timeout)}
    elif meter is not None:
        io = {"kind": "meter"}
        io.update(_attrs(meter, ["address", "method"]))
        out["io"] = io

    return out


def ln0_private(ln0_elem):
    """LN0/Private/oc:iedSettings + oc:interlock[] + oc:remoteTrip[] + oc:*Scheme[]
    -> {iedSettings={...}, interlocks=[...], remoteTrips=[...], protection={...}}.
    """
    priv = find_private(ln0_elem)
    result = {"iedSettings": {}, "interlocks": [], "remoteTrips": [],
              "protection": {"ptoc": [], "pdif": [], "pdis": []}}
    if priv is None:
        return result

    settings_elem = priv.find(oc_q("iedSettings"))
    if settings_elem is not None:
        result["iedSettings"] = _attrs(settings_elem, [
            "tickIntervalSec", "integritySec", "gooseStaleAfterSec", "mmsPort",
            "hmsPort", "resyncSec", "connectTimeoutSec", "reconnectIntervalSec",
        ], numeric=_IED_SETTINGS_NUMERIC)

    for il in priv.findall(oc_q("interlock")):
        result["interlocks"].append(_attrs(il, [
            "id", "localRef", "blockValue", "peerIed", "peerRef",
            "condition", "peerValue", "failOpen", "staleAfterSec",
        ], numeric=_INTERLOCK_NUMERIC))

    for rt in priv.findall(oc_q("remoteTrip")):
        result["remoteTrips"].append(_attrs(rt, [
            "id", "peerIed", "peerRef", "condition", "peerValue",
            "localRef", "tripValue",
        ]))

    for ptoc_elem in priv.findall(oc_q("ptocScheme")):
        entry = _attrs(ptoc_elem, [
            "name", "input", "trip", "pickup", "curve", "timeMultiplier",
            "definiteTimeSec", "resetSec", "respectInterlocks",
        ], numeric=_PTOC_NUMERIC)
        result["protection"]["ptoc"].append(entry)

    for pdif_elem in priv.findall(oc_q("pdifScheme")):
        entry = _attrs(pdif_elem, [
            "name", "minPickup", "restraintSlope", "respectInterlocks",
        ], numeric=_PDIF_NUMERIC)
        inputs = []
        for inp in pdif_elem.findall(oc_q("input")):
            inputs.append(_attrs(inp, ["ref", "scale"], numeric=_PDIF_INPUT_NUMERIC))
        entry["inputs"] = inputs
        result["protection"]["pdif"].append(entry)

    for pdis_elem in priv.findall(oc_q("pdisScheme")):
        entry = _attrs(pdis_elem, [
            "name", "zone1ReachOhms", "zone1DelaySec",
            "zone2ReachOhms", "zone2DelaySec",
        ], numeric=_PDIS_NUMERIC)
        result["protection"]["pdis"].append(entry)

    return result


def subnetwork_private(subnetwork_elem):
    """SubNetwork/Private/oc:transport -> {gooseGroup=..., gooseGroupPort=...} or {}.

    gooseGroup is an OC-IP-Stack "subnet.host" string (e.g. "255.10"), NOT
    a decimal -- must stay a string, never numeric-coerced.
    """
    priv = find_private(subnetwork_elem)
    if priv is None:
        return {}
    transport = priv.find(oc_q("transport"))
    if transport is None:
        return {}
    return _attrs(transport, ["gooseGroup", "gooseGroupPort"], numeric=_TRANSPORT_NUMERIC)


def report_control_private(rc_elem):
    """ReportControl/Private/oc:reportSettings -> {periodSec=...} or {}."""
    priv = find_private(rc_elem)
    if priv is None:
        return {}
    settings = priv.find(oc_q("reportSettings"))
    if settings is None:
        return {}
    return _attrs(settings, ["periodSec"], numeric=_REPORT_SETTINGS_NUMERIC)


def connected_ap_private(connectedap_elem):
    """ConnectedAP/Private/oc:mmsAddress -> {address=...} or {}.

    Carries this IED's OC-IP-Stack "subnet.host" address for the MMS-lite
    TCP link -- real SCL's Address/P[@type="IP"] is IPv4-dotted-quad only
    (see tP_IP's pattern restriction in the vendored schema) and doesn't
    fit OC-IP-Stack's informal subnet.host addressing, so this stays a
    Private field rather than a misuse of the real IP P-element. `address`
    is a string ("1.10"), never numeric-coerced -- same reasoning as
    subnetwork_private's gooseGroup.
    """
    priv = find_private(connectedap_elem)
    if priv is None:
        return {}
    addr_elem = priv.find(oc_q("mmsAddress"))
    if addr_elem is None:
        return {}
    return _attrs(addr_elem, ["address"])


def scada_private(ln0_elem):
    """SCADA IED's LN0/Private -> {historian={...}, alarms=[...]}, layered
    on top of ln0_private's iedSettings/interlocks/etc (SCADA's cfg has no
    interlocks/protection/remoteTrips, but reuses iedSettings for
    tickIntervalSec/resyncSec/connectTimeoutSec/reconnectIntervalSec/
    gooseStaleAfterSec/hmsPort).
    """
    priv = find_private(ln0_elem)
    result = {"historian": {}, "alarms": []}
    if priv is None:
        return result

    hist_elem = priv.find(oc_q("historian"))
    if hist_elem is not None:
        result["historian"] = _attrs(hist_elem, ["dir", "maxBytes", "maxFiles"], numeric=_HISTORIAN_NUMERIC)

    for alarm_elem in priv.findall(oc_q("alarm")):
        entry = _attrs(alarm_elem, ["id", "ref", "condition", "severity", "message"])
        raw_value = alarm_elem.get("value")
        if raw_value is not None:
            # Genuinely number-or-string (a threshold like 200, or a status
            # like "open") -- the one field where guessing is unavoidable.
            low = raw_value.strip().lower()
            if low in ("true", "false"):
                entry["value"] = low == "true"
            else:
                entry["value"] = _coerce_numeric(raw_value)
        result["alarms"].append(entry)

    return result


def gse_timing_private(gse_elem):
    """GSE/Private/oc:gooseTiming override -> {burstIntervalsSec=[...]} or {}.

    Real SCL's GSE/MinTime+MaxTime only give two numbers (fastest retransmit,
    steady heartbeat); a full burst-interval ladder has no standard home.
    """
    priv = find_private(gse_elem)
    if priv is None:
        return {}
    timing = priv.find(oc_q("gooseTiming"))
    if timing is None:
        return {}
    out = {}
    burst = timing.get("burstIntervalsSec")
    if burst is not None:
        out["burstIntervalsSec"] = [float(x) for x in burst.split(",")]
    return out
