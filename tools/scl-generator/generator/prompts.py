"""Validated `input()` wrappers: every prompt re-asks on bad input rather
than crashing, and every prompt with a default accepts a blank line to
take it -- what keeps a minimal single-diameter station a short wizard
session (see wizard.py).
"""

from typing import Callable, List, Optional, Tuple


def ask_str(prompt: str, default: Optional[str] = None,
            validate: Optional[Callable[[str], None]] = None) -> str:
    suffix = " [%s]" % default if default is not None else ""
    while True:
        raw = input("%s%s: " % (prompt, suffix)).strip()
        if not raw:
            if default is not None:
                return default
            print("  a value is required")
            continue
        if validate:
            try:
                validate(raw)
            except Exception as e:
                print("  %s" % e)
                continue
        return raw


def ask_int(prompt: str, default: Optional[int] = None,
            min_value: Optional[int] = None, max_value: Optional[int] = None) -> int:
    suffix = " [%s]" % default if default is not None else ""
    while True:
        raw = input("%s%s: " % (prompt, suffix)).strip()
        if not raw and default is not None:
            return default
        try:
            value = int(raw)
        except ValueError:
            print("  enter a whole number")
            continue
        if min_value is not None and value < min_value:
            print("  must be at least %d" % min_value)
            continue
        if max_value is not None and value > max_value:
            print("  must be at most %d" % max_value)
            continue
        return value


def ask_float(prompt: str, default: Optional[float] = None,
              min_value: Optional[float] = None) -> float:
    suffix = " [%s]" % default if default is not None else ""
    while True:
        raw = input("%s%s: " % (prompt, suffix)).strip()
        if not raw and default is not None:
            return default
        try:
            value = float(raw)
        except ValueError:
            print("  enter a number")
            continue
        if min_value is not None and value <= min_value:
            print("  must be greater than %s" % min_value)
            continue
        return value


def ask_yes_no(prompt: str, default: bool = True) -> bool:
    suffix = " [Y/n]" if default else " [y/N]"
    while True:
        raw = input("%s%s: " % (prompt, suffix)).strip().lower()
        if not raw:
            return default
        if raw in ("y", "yes"):
            return True
        if raw in ("n", "no"):
            return False
        print("  enter y or n")


def ask_choice(prompt: str, options: List[Tuple[object, str, str]],
                default_index: int = 0):
    """`options` is a list of (value, label, help_text). Prints a
    numbered menu (help text on the following indented line) and returns
    the chosen `value`. Blank input takes `options[default_index]`.
    """
    print(prompt)
    for i, (_value, label, help_text) in enumerate(options, start=1):
        marker = "*" if (i - 1) == default_index else " "
        print("  %s%d) %s" % (marker, i, label))
        if help_text:
            print("       %s" % help_text)
    while True:
        raw = input("Choice [%d]: " % (default_index + 1)).strip()
        if not raw:
            return options[default_index][0]
        try:
            idx = int(raw) - 1
        except ValueError:
            print("  enter a number from the list")
            continue
        if 0 <= idx < len(options):
            return options[idx][0]
        print("  choose a number between 1 and %d" % len(options))
