"""
Block 1 — Find your instruments.

Run:  python -m psu_test.discover

Beyond the document's `print(rm.list_resources())`, this queries *IDN? on
each resource so you get "which box is this" rather than a list of opaque
serial numbers to guess between. Resources that fail to open are reported
with the reason instead of raising, since a busy or permission-denied VISA
session is the usual cause and the message tells you which.
"""

from __future__ import annotations

import sys


def discover(timeout_ms: int = 2000) -> list[tuple[str, str]]:
    """Return [(resource_string, idn_or_error)] for every visible instrument."""
    try:
        import pyvisa
    except ImportError:
        print("pyvisa is not installed. pip install -r requirements.txt",
              file=sys.stderr)
        return []

    rm = pyvisa.ResourceManager()
    found = []
    for res in rm.list_resources():
        try:
            inst = rm.open_resource(res)
            inst.timeout = timeout_ms
            idn = inst.query("*IDN?").strip()
            inst.close()
        except Exception as exc:  # noqa: BLE001 - report, never abort the scan
            idn = f"<no response: {type(exc).__name__}: {exc}>"
        found.append((res, idn))
    return found


def main() -> int:
    results = discover()
    if not results:
        print("No VISA resources found.")
        print("Checks: instrument powered and in USBTMC/LAN mode; "
              "udev rules on Linux; pyvisa-py installed if you have no "
              "vendor VISA runtime.")
        return 1
    width = max(len(r) for r, _ in results)
    print(f"{'RESOURCE'.ljust(width)}  IDENTITY")
    print(f"{'-' * width}  {'-' * 40}")
    for res, idn in results:
        print(f"{res.ljust(width)}  {idn}")
    print("\nCopy the relevant strings into config/bench.yaml.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
