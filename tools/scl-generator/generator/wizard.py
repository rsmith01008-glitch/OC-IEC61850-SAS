"""The interactive flow: prompts.py + topology.py + layouts/* -> a
completed Station. No topology math of its own -- every layout
question is answered by calling straight into generator.layouts'
builders and generator.naming's validators, so this module stays pure
orchestration. See tools/scl-generator/README.md for a full example
session transcript.
"""

from . import prompts, naming
from .topology import (
    Tap, TapKind, LayoutKind, Transformer, Station,
    ProtectionDefaults, NetworkDefaults, IedSettingsDefaults, ScadaDefaults,
)
from .layouts import LAYOUT_BUILDERS

_LAYOUT_MENU = [
    (LayoutKind.BREAKER_AND_HALF, "1½-breaker",
     "3 breakers per diameter, 2 taps per diameter -- needs an even tap count."),
    (LayoutKind.SINGLE_BUS, "Single/main bus",
     "One bus, one breaker per tap -- the simplest arrangement."),
    (LayoutKind.MAIN_AND_TRANSFER, "Main-and-transfer bus",
     "Main bus + transfer bus + one tie breaker."),
    (LayoutKind.RING_BUS, "Ring bus",
     "Breakers form a closed loop -- needs at least 3 taps to close it."),
]

_TAP_KIND_MENU = [
    (TapKind.LINE, "line", "An incoming/outgoing transmission line."),
    (TapKind.FEEDER, "feeder", "An outgoing distribution feeder."),
    (TapKind.TRANSFORMER, "transformer", "A power transformer winding terminal (paired up later)."),
]

# The real curve name set (sas/protection/curves.lua's FORMULAS table)
# plus DEFINITE_TIME (handled specially in sas/protection/ptoc.lua, not
# a curve.lua formula) -- kept as a plain literal here rather than
# parsing the Lua source, since this tool never runs alongside that
# runtime code and the two are meant to be cross-checked by a human
# reading both, not coupled at import time.
_CURVE_MENU = [
    ("IEC_VERY_INVERSE", "IEC very inverse (default)", ""),
    ("IEC_STANDARD_INVERSE", "IEC standard inverse", ""),
    ("IEC_EXTREMELY_INVERSE", "IEC extremely inverse", ""),
    ("IEEE_MOD_INVERSE", "IEEE moderately inverse", ""),
    ("IEEE_VERY_INVERSE", "IEEE very inverse", ""),
    ("IEEE_EXTREME_INVERSE", "IEEE extremely inverse", ""),
    ("DEFINITE_TIME", "Definite time (fixed delay, not curve-based)", ""),
]


def _collect_taps():
    taps = []
    tap_num = 0
    while True:
        tap_num += 1
        raw_name = input("  Tap %d name (blank to finish this voltage level): " % tap_num).strip()
        if not raw_name:
            return taps
        try:
            naming.validate_identifier(raw_name)
        except naming.NameError_ as e:
            print("    %s" % e)
            tap_num -= 1
            continue
        kind = prompts.ask_choice("  Tap kind?", _TAP_KIND_MENU)
        taps.append(Tap(raw_name, kind))


def _build_voltage_level(vl_num: int, start_index: int):
    print("\n--- Voltage level %d ---" % vl_num)
    vl_name = prompts.ask_str("Voltage level name", default="V%d" % vl_num,
                               validate=naming.validate_identifier)
    kv = prompts.ask_float("Nominal kV", min_value=0)
    layout_kind = prompts.ask_choice("Layout kind for this voltage level?", _LAYOUT_MENU)

    while True:
        taps = _collect_taps()
        builder = LAYOUT_BUILDERS[layout_kind]
        try:
            return builder(vl_name, kv, taps, start_index=start_index)
        except ValueError as e:
            print("  %s -- let's redo this voltage level's taps." % e)


def _collect_voltage_levels():
    vls = []
    breaker_index = 1
    vl_num = 0
    while True:
        vl_num += 1
        vl = _build_voltage_level(vl_num, breaker_index)
        vls.append(vl)
        breaker_index += len(vl.breakers)
        if not prompts.ask_yes_no("\nAdd another voltage level?", default=False):
            return vls


def _collect_transformers(vls):
    unclaimed = [(vl, tap) for vl in vls for tap in vl.taps if tap.kind == TapKind.TRANSFORMER]
    if not unclaimed:
        return []

    print("\n--- Transformers ---")
    print("%d unclaimed transformer tap(s) need pairing into transformers." % len(unclaimed))
    transformers = []
    xfmr_num = 0
    while unclaimed:
        xfmr_num += 1
        name = prompts.ask_str("Transformer name", default="XFMR%d" % xfmr_num,
                                validate=naming.validate_ied_name)

        hv_menu = [((vl, tap), "%s / %s (%g kV)" % (vl.vl_name, tap.name, vl.kv), "")
                   for vl, tap in unclaimed]
        hv_vl, hv_tap = prompts.ask_choice("  Pick the HV-side tap:", hv_menu)

        lv_candidates = [(vl, tap) for vl, tap in unclaimed if vl is not hv_vl]
        if not lv_candidates:
            print("  No other voltage level has an unclaimed transformer tap left to pair "
                  "%s/%s with -- leaving it unclaimed." % (hv_vl.vl_name, hv_tap.name))
            unclaimed.remove((hv_vl, hv_tap))
            xfmr_num -= 1
            continue
        lv_menu = [((vl, tap), "%s / %s (%g kV)" % (vl.vl_name, tap.name, vl.kv), "")
                   for vl, tap in lv_candidates]
        lv_vl, lv_tap = prompts.ask_choice("  Pick the LV-side tap:", lv_menu)

        if hv_vl.kv <= lv_vl.kv:
            print("  %s (%gkV) is not higher than %s (%gkV) -- swapping HV/LV."
                  % (hv_vl.vl_name, hv_vl.kv, lv_vl.vl_name, lv_vl.kv))
            hv_vl, hv_tap, lv_vl, lv_tap = lv_vl, lv_tap, hv_vl, hv_tap

        xfmr = Transformer(
            name=name, hv_vl=hv_vl, hv_tap=hv_vl.tap_node_for(hv_tap),
            lv_vl=lv_vl, lv_tap=lv_vl.tap_node_for(lv_tap),
        )
        transformers.append(xfmr)
        print("  %s: HV scale %.3f, LV scale %.3f" % (xfmr.name, xfmr.scale_hv, xfmr.scale_lv))
        unclaimed.remove((hv_vl, hv_tap))
        unclaimed.remove((lv_vl, lv_tap))

    if unclaimed:
        names = ", ".join("%s/%s" % (vl.vl_name, tap.name) for vl, tap in unclaimed)
        raise RuntimeError(
            "Transformer taps left unpaired: %s -- re-run the wizard and either give them "
            "a matching partner tap on a different voltage level, or make them line/feeder "
            "taps instead." % names
        )
    return transformers


def _collect_protection_defaults() -> ProtectionDefaults:
    print("\n--- Protection defaults (applied to every breaker/transformer) ---")
    pickup = prompts.ask_float("PTOC pickup (amps)", default=1.2, min_value=0)
    curve = prompts.ask_choice("PTOC curve?", _CURVE_MENU)
    if curve == "DEFINITE_TIME":
        time_multiplier = 0.3
        definite_time_sec = prompts.ask_float("PTOC definite time delay (sec)", default=0.5, min_value=0)
    else:
        time_multiplier = prompts.ask_float("PTOC time multiplier", default=0.3, min_value=0)
        definite_time_sec = 0.5
    reset_sec = prompts.ask_float("PTOC reset decay (sec)", default=0.1, min_value=0)
    min_pickup = prompts.ask_float("PDIF minimum pickup (amps)", default=0.2, min_value=0)
    restraint_slope = prompts.ask_float("PDIF restraint slope", default=0.4, min_value=0)
    return ProtectionDefaults(
        ptoc_pickup=pickup, ptoc_curve=curve, ptoc_time_multiplier=time_multiplier,
        ptoc_definite_time_sec=definite_time_sec, ptoc_reset_sec=reset_sec,
        pdif_min_pickup=min_pickup, pdif_restraint_slope=restraint_slope,
    )


def _collect_network_defaults() -> NetworkDefaults:
    print("\n--- GOOSE / network defaults ---")
    goose_group = prompts.ask_str("GOOSE multicast group (subnet.host)", default="255.10")
    goose_group_port = prompts.ask_int("GOOSE port", default=8104, min_value=1)
    mms_subnet = prompts.ask_int("MMS subnet", default=1, min_value=0)
    mms_host_start_breakers = prompts.ask_int("First MMS host number for breaker IEDs", default=11, min_value=0)
    mms_host_start_transformers = prompts.ask_int("First MMS host number for transformer IEDs", default=20, min_value=0)
    scada_mms_host = None
    if prompts.ask_yes_no("Give SCADA its own oc:mmsAddress/GSE binding?", default=False):
        scada_mms_host = prompts.ask_int("SCADA's MMS host number", default=1, min_value=0)
    mac_prefix = prompts.ask_str("MAC address prefix", default="01-0C-CD-01-00-")
    appid_base = prompts.ask_int("APPID base number", default=1, min_value=0)
    vlan_id = prompts.ask_str("VLAN ID", default="000")
    vlan_priority_breaker = prompts.ask_int("VLAN priority for breaker IEDs (0-7)", default=4, min_value=0, max_value=7)
    vlan_priority_transformer = prompts.ask_int("VLAN priority for transformer IEDs (0-7)", default=6, min_value=0, max_value=7)
    gse_min_time_ms = prompts.ask_int("GOOSE MinTime (ms)", default=100, min_value=1)
    gse_max_time_ms = prompts.ask_int("GOOSE MaxTime (ms)", default=5000, min_value=1)
    return NetworkDefaults(
        goose_group=goose_group, goose_group_port=goose_group_port, mms_subnet=mms_subnet,
        mms_host_start_breakers=mms_host_start_breakers,
        mms_host_start_transformers=mms_host_start_transformers,
        scada_mms_host=scada_mms_host, mac_prefix=mac_prefix, appid_base=appid_base,
        vlan_id=vlan_id, vlan_priority_breaker=vlan_priority_breaker,
        vlan_priority_transformer=vlan_priority_transformer,
        gse_min_time_ms=gse_min_time_ms, gse_max_time_ms=gse_max_time_ms,
    )


def _collect_ied_settings_defaults() -> IedSettingsDefaults:
    print("\n--- IED settings defaults ---")
    tick_interval_sec = prompts.ask_float("Tick interval (sec)", default=0.2, min_value=0)
    integrity_sec = prompts.ask_int("Integrity refresh interval (sec)", default=30, min_value=1)
    goose_stale_after_sec = prompts.ask_int("GOOSE stale-after (sec)", default=15, min_value=1)
    mms_port = prompts.ask_int("MMS port (breaker/transformer IEDs)", default=8102, min_value=1)
    hms_port = prompts.ask_int("HMS port (SCADA)", default=8103, min_value=1)
    resync_sec = prompts.ask_int("SCADA resync interval (sec)", default=60, min_value=1)
    connect_timeout_sec = prompts.ask_int("SCADA connect timeout (sec)", default=5, min_value=1)
    reconnect_interval_sec = prompts.ask_int("SCADA reconnect interval (sec)", default=10, min_value=1)
    return IedSettingsDefaults(
        tick_interval_sec=tick_interval_sec, integrity_sec=integrity_sec,
        goose_stale_after_sec=goose_stale_after_sec, mms_port=mms_port, hms_port=hms_port,
        resync_sec=resync_sec, connect_timeout_sec=connect_timeout_sec,
        reconnect_interval_sec=reconnect_interval_sec,
    )


def _collect_scada_defaults(has_transformers: bool) -> ScadaDefaults:
    print("\n--- SCADA ---")
    ied_name = prompts.ask_str("SCADA IED name", default="SCADA1", validate=naming.validate_ied_name)
    historian_dir = prompts.ask_str("Historian directory", default="/var/log/sas-scada")
    historian_max_bytes = prompts.ask_int("Historian max bytes per file", default=262144, min_value=1)
    historian_max_files = prompts.ask_int("Historian max files", default=5, min_value=1)
    auto_undervoltage_alarms = prompts.ask_yes_no("Auto-generate per-bus undervoltage alarms?", default=True)
    undervoltage_ratio = 0.9
    if auto_undervoltage_alarms:
        undervoltage_ratio = prompts.ask_float("Undervoltage alarm ratio (of nominal kV)", default=0.9, min_value=0)
    auto_trip_alarms = True
    if has_transformers:
        auto_trip_alarms = prompts.ask_yes_no("Auto-generate a trip alarm per transformer's PDIF.Op?", default=True)
    return ScadaDefaults(
        ied_name=ied_name, historian_dir=historian_dir, historian_max_bytes=historian_max_bytes,
        historian_max_files=historian_max_files, auto_undervoltage_alarms=auto_undervoltage_alarms,
        undervoltage_ratio=undervoltage_ratio, auto_trip_alarms=auto_trip_alarms,
    )


def _print_summary(station: Station):
    n_breakers = sum(len(vl.breakers) for vl in station.voltage_levels)
    print("\n--- Summary ---")
    print("Substation: %s" % station.name)
    for vl in station.voltage_levels:
        print("  %s: %g kV, %s, %d tap(s), %d breaker(s)"
              % (vl.vl_name, vl.kv, vl.layout_kind.value, len(vl.taps), len(vl.breakers)))
    print("Transformers: %d" % len(station.transformers))
    for xfmr in station.transformers:
        print("  %s: %s (%gkV) <-> %s (%gkV)"
              % (xfmr.name, xfmr.hv_vl.vl_name, xfmr.hv_vl.kv, xfmr.lv_vl.vl_name, xfmr.lv_vl.kv))
    print("Total breaker IEDs: %d" % n_breakers)
    print("SCADA IED: %s" % station.scada.ied_name)

    for vl in station.voltage_levels:
        if vl.layout_kind == LayoutKind.MAIN_AND_TRANSFER:
            print("\nNote: %s (main-and-transfer) does not model the per-bay transfer-bus "
                  "bypass disconnect -- see tools/scl-generator/README.md's Scoping decisions."
                  % vl.vl_name)


def run_wizard() -> "Station | None":
    """Runs the full interactive flow. Returns a completed Station, or
    None if the user declines the final confirmation.
    """
    print("=== OC-IEC61850-SAS SCL generator ===")
    print("Answers with a default shown in [brackets] can be left blank.\n")

    station_name = prompts.ask_str("Substation name", validate=naming.validate_identifier)
    voltage_levels = _collect_voltage_levels()
    transformers = _collect_transformers(voltage_levels)
    protection = _collect_protection_defaults()
    network = _collect_network_defaults()
    ied_settings = _collect_ied_settings_defaults()
    scada = _collect_scada_defaults(has_transformers=bool(transformers))

    station = Station(
        name=station_name, voltage_levels=voltage_levels, transformers=transformers,
        protection=protection, network=network, ied_settings=ied_settings, scada=scada,
    )
    _print_summary(station)

    if not prompts.ask_yes_no("\nGenerate now?", default=True):
        return None
    return station
