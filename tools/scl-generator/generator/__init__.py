"""Interactive SCL generator: an input()-driven wizard that turns answers
about substation layout (voltage levels, bus/switching arrangement, bay
taps, transformers) into an IEC 61850-6 SCL `.scd` file plus a one-line
diagram -- so building a new switchyard never requires hand-writing SCL
XML. Offline, build-time only, never runs on OC hardware, same as
tools/scl-compiler/ (which this tool's output is meant to feed).
"""
