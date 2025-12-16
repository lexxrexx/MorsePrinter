#!/usr/bin/env python3
"""
Morse‑to‑Receipt Printer (real‑time conversation printing)

All user‑adjustable parameters are read from `config.yaml`:
    • filter_enabled / call_sign
    • frequency_hz, gain
    • printer_vendor_id, printer_product_id, printer_interface

Behaviour
---------
* Keep a 15‑second rolling buffer at all times.
* When a line contains the configured call‑sign we do NOT print it.
  Instead we wait for a response from another station – any line that
  contains a call‑sign different from the configured one.
* Upon the first valid response:
    1. Flush the rolling buffer (minus any lines that still contain the
       configured call‑sign) to the printer (lead‑in).
    2. Print the response line.
    3. From now on, print every subsequent line in real‑time.
* Stop printing when a QSO‑termination token (73, SK, RR, DIT DIT, …)
  is detected, cut the paper, and reset.
* If `filter_enabled` is false, every decoded line is printed
  immediately (original behaviour).

Dependencies (install via apt/pip):
    rtl_sdr, sox, multimon-ng, python‑escpos, pyyaml
"""

import subprocess
import sys
import yaml               # pip install pyyaml
from escpos.printer import Usb
import os
import re
import time
import collections

# ----------------------------------------------------------------------
# Default values (used if a key is missing from config.yaml)
# ----------------------------------------------------------------------
DEFAULTS = {
    "filter_enabled": False,
    "call_sign": "",

    "frequency_hz": 14_070_000,   # 14.070 MHz
    "gain": 40,                  # RTL‑SDR gain (0‑49)

    "printer_vendor_id": 0x04b8,   # Example: Epson vendor ID
    "printer_product_id": 0x0202,  # Example: TM‑T20II product ID
    "printer_interface": 0,        # Usually 0
}

# ----------------------------------------------------------------------
# Load configuration (merge defaults with user‑provided values)
# ----------------------------------------------------------------------
def load_config():
    cfg_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    config = DEFAULTS.copy()

    if not os.path.isfile(cfg_path):
        return config

    try:
        with open(cfg_path, "r") as f:
            user_cfg = yaml.safe_load(f) or {}
        # Override defaults with any user‑provided keys
        for key, val in user_cfg.items():
            if key in config:
                # Cast numeric hex strings (e.g., "0x04b8") to int if needed
                if key.startswith("printer_") and isinstance(val, str):
                    try:
                        config[key] = int(val, 0)   # handles 0x… notation
                    except ValueError:
                        config[key] = val
                else:
                    config[key] = val
        return config
    except Exception as e:
        sys.stderr.write(f"⚠️  Failed to read config.yaml ({e}); using defaults.\n")
        return config


# ----------------------------------------------------------------------
# Start the rtl_fm → sox → multimon-ng pipeline
# ----------------------------------------------------------------------
def start_rtl_fm(freq_hz: int, gain: int):
    rtl_cmd = ["rtl_fm", "-f", str(freq_hz), "-s", "22050", "-g", str(gain), "-"]
    sox_cmd = [
        "sox",
        "-t", "raw",
        "-r", "22050",
        "-e", "signed",
        "-b", "16",
        "-c", "1",
        "-",
        "-t", "wav",
        "-",
    ]
    multimon_cmd = ["multimon-ng", "-a", "CW", "-t", "wav", "-"]

    rtl = subprocess.Popen(rtl_cmd, stdout=subprocess.PIPE)
    sox = subprocess.Popen(sox_cmd, stdin=rtl.stdout, stdout=subprocess.PIPE)
    multimon = subprocess.Popen(
        multimon_cmd,
        stdin=sox.stdout,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        bufsize=1,
    )
    return multimon


# ----------------------------------------------------------------------
# Initialise the ESC/POS printer (fails gracefully)
# ----------------------------------------------------------------------
def init_printer(vendor_id: int, product_id: int, interface: int):
    try:
        return Usb(vendor_id, product_id, interface=interface)
    except Exception as e:
        sys.stderr.write(f"❌ Could not open printer: {e}\n")
        # Dummy printer that silently discards output
        class DummyPrinter:
            def text(self, *_args, **_kwargs): pass
            def cut(self, *_args, **_kwargs): pass
            def close(self): pass
        return DummyPrinter()


# ----------------------------------------------------------------------
# QSO termination detection
# ----------------------------------------------------------------------
TERMINATION_TOKENS = {
    "73", "SK", "RR", "END OF CALL", "END OF CONTACT",
    "DIT DIT", "DIT DIT DIT", "DE", "73+", "73!"
}
TERMINATION_REGEX = re.compile(
    r"\b(" + "|".join(map(re.escape, TERMINATION_TOKENS)) + r")\b",
    re.I,
)


def is_termination(line: str) -> bool:
    """True if the line looks like a QSO termination token."""
    return bool(TERMINATION_REGEX.search(line))


# ----------------------------------------------------------------------
# Helper: extract all call‑sign‑like tokens from a line
# ----------------------------------------------------------------------
CALLSIGN_REGEX = re.compile(r"[A-Z0-9]{1,2}[0-9][A-Z0-9]{1,4}(?:/[A-Z0-9]+)?", re.I)

def extract_callsigns(text: str) -> set:
    """Return a set of unique call‑sign strings found in the text."""
    return {cs.upper() for cs in CALLSIGN_REGEX.findall(text)}


# ----------------------------------------------------------------------
# Helper: does a line contain the configured call sign?
# ----------------------------------------------------------------------
def contains_callsign(line: str, cfg: dict) -> bool:
    if not cfg["filter_enabled"] or not cfg["call_sign"]:
        return False
    return cfg["call_sign"] in line.upper()


# ----------------------------------------------------------------------
# Helper: is this line a *valid* response from another station?
# ----------------------------------------------------------------------
def is_valid_response(line: str, cfg: dict) -> bool:
    """
    A valid response is any line that contains at least ONE call‑sign
    that is DIFFERENT from the configured call‑sign.
    The line does NOT need to contain the configured call‑sign itself.
    """
    all_calls = extract_callsigns(line)
    all_calls.discard(cfg["call_sign"])
    return len(all_calls) > 0


# ----------------------------------------------------------------------
# Main loop – decode, rolling buffer, response detection, real‑time printing
# ----------------------------------------------------------------------
def main():
    cfg = load_config()

    # ------------------------------------------------------------
    # Print a short status line showing the loaded configuration
    # ------------------------------------------------------------
    if cfg["filter_enabled"]:
        print(f"Filter enabled – waiting for a response to '{cfg['call_sign']}'.")
    else:
        print("Filter disabled – printing every decoded line.")
    print(f"Using frequency {cfg['frequency_hz']} Hz, gain {cfg['gain']}.")
    print(f"Printer IDs – vendor: 0x{cfg['printer_vendor_id']:04x}, "
          f"product: 0x{cfg['printer_product_id']:04x}, interface: {cfg['printer_interface']}")

    # ------------------------------------------------------------
    # Initialise hardware
    # ------------------------------------------------------------
    printer = init_printer(
        cfg["printer_vendor_id"],
        cfg["printer_product_id"],
        cfg["printer_interface"]
    )
    decoder = start_rtl_fm(cfg["frequency_hz"], cfg["gain"])

    # ----- STATE ---------------------------------------------------------
    rolling_buffer = collections.deque()   # (timestamp, line) – 15 sec window
    ROLLING_WINDOW = 15.0                # seconds

    awaiting_response = False   # Call sign heard, waiting for a reply
    printing_active = False     # True once we start real‑time printing

    print("🛰️  Listening for Morse… Press Ctrl‑C to stop.")
    try:
        for raw_line in decoder.stdout:
            raw_line = raw_line.strip()
            if not raw_line:
                continue

            # multimon-ng prefixes each line with the mode, e.g. "CW: SOS"
            if not raw_line.startswith("CW:"):
                continue

            msg = raw_line[3:].strip()   # strip the leading "CW:"
            if not msg:
                continue

            # Echo to console for debugging / visibility
            print(f"📡 Received: {msg}")

            # ----------------------------------------------------------------
            # FILTER DISABLED → immediate printing (original behaviour)
            # ----------------------------------------------------------------
            if not cfg["filter_enabled"]:
                try:
                    printer.text(msg + "\n")
                    printer.cut()
                except Exception as e:
                    sys.stderr.write(f"⚠️  Printer error (disabled mode): {e}\n")
                continue

            # ----------------------------------------------------------------
            # FILTER ENABLED – maintain the rolling 15‑second buffer
            # ----------------------------------------------------------------
            now = time.time()
            rolling_buffer.append((now, msg))
            while rolling_buffer and now - rolling_buffer[0][0] > ROLLING_WINDOW:
                rolling_buffer.popleft()

            # ----------------------------------------------------------------
            # STATE MACHINE
            # ----------------------------------------------------------------
            # 1️⃣ Not currently printing a QSO
            if not printing_active:
                # a) Have we already heard the call sign and are waiting?
                if awaiting_response:
                    # Check for a *valid* response from another station
                    if is_valid_response(msg, cfg):
                        # ---- VALID RESPONSE DETECTED ----
                        printing_active = True
                        awaiting_response = False

                        # Flush the rolling buffer **excluding** any lines that still contain the call sign
                        lead_in = [
                            line for _, line in rolling_buffer
                            if not contains_callsign(line, cfg)
                        ]
                        if lead_in:
                            try:
                                printer.text("\n".join(lead_in) + "\n")
                                printer.cut()
                            except Exception as e:
                                sys.stderr.write(f"⚠️  Printer error (lead‑in): {e}\n")

                        # Print the response line itself (real‑time mode starts here)
                        try:
                            printer.text(msg + "\n")
                            printer.cut()
                        except Exception as e:
                            sys.stderr.write(f"⚠️  Printer error (response): {e}\n")
                        continue  # now in real‑time mode

                    # If the line does NOT contain a different call sign, keep waiting
                    continue

                # b) Haven't seen the call sign yet – look for it
                if contains_callsign(msg, cfg):
                    awaiting_response = True
                    # Do NOT print anything yet; keep the rolling buffer intact
                    continue

                # c) Nothing relevant – stay idle
                continue

            # ----------------------------------------------------------------
            # We ARE actively printing a QSO (printing_active == True)
            # ----------------------------------------------------------------
            try:
                printer.text(msg + "\n")
                printer.cut()
            except Exception as e:
                sys.stderr.write(f"⚠️  Printer error (active QSO): {e}\n")

            # End of QSO?
            if is_termination(msg):
                # Stop real‑time printing and reset state
                printing_active = False
                awaiting_response = False
                rolling_buffer.clear()   # optional – start fresh after a QSO

    except KeyboardInterrupt:
        print("\n👋 Stopping…")
    finally:
        # Close printer gracefully; ignore any errors here as well
        try:
            printer.close()
        except Exception:
            pass
        decoder.terminate()


if __name__ == "__main__":
    main()