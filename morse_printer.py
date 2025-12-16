#!/usr/bin/env python3
"""
Morse‑to‑Receipt Printer (real‑time conversation printing)

Behaviour
---------
* Keep a 15‑second rolling buffer at all times.
* When a line **contains the configured call‑sign** we do NOT print it.
  Instead we wait for a **response** – any line that does NOT contain the same
  call‑sign.
* As soon as the first response arrives:
    1. Flush the rolling buffer **minus** any lines that contain the call‑sign.
    2. Print the response line.
    3. Continue printing every subsequent line in real‑time.
* Stop printing when a QSO‑termination token (73, SK, RR, DIT DIT, …) is seen,
  cut the paper, and reset.
* If `filter_enabled` is false, every line is printed immediately
  (original behaviour).

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
# USER SETTINGS – adapt to your hardware
# ----------------------------------------------------------------------
FREQ_HZ = 14_070_000          # Frequency in Hz (e.g., 14.070 MHz)
GAIN = 40                     # RTL‑SDR gain (0‑49)

# USB IDs – replace with values from `lsusb`
PRINTER_VENDOR_ID = 0x04b8    # Your vendor ID
PRINTER_PRODUCT_ID = 0x0202   # Your product ID
PRINTER_INTERFACE = 0         # Usually 0
# ----------------------------------------------------------------------


# ----------------------------------------------------------------------
# Load optional YAML configuration (filter on/off + call sign)
# ----------------------------------------------------------------------
def load_config():
    cfg_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    default_cfg = {"filter_enabled": False, "call_sign": ""}

    if not os.path.isfile(cfg_path):
        return default_cfg

    try:
        with open(cfg_path, "r") as f:
            data = yaml.safe_load(f) or {}
        enabled = bool(data.get("filter_enabled", False))
        cs = str(data.get("call_sign", "")).strip().upper()
        return {"filter_enabled": enabled, "call_sign": cs}
    except Exception as e:
        sys.stderr.write(f"⚠️  Failed to read config.yaml ({e}); using defaults.\n")
        return default_cfg


# ----------------------------------------------------------------------
# Start the rtl_fm → sox → multimon-ng pipeline
# ----------------------------------------------------------------------
def start_rtl_fm():
    rtl_cmd = ["rtl_fm", "-f", str(FREQ_HZ), "-s", "22050", "-g", str(GAIN), "-"]
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
# Initialise the ESC/POS printer – **errors are logged but do not abort**
# ----------------------------------------------------------------------
def init_printer():
    try:
        return Usb(PRINTER_VENDOR_ID, PRINTER_PRODUCT_ID, interface=PRINTER_INTERFACE)
    except Exception as e:
        sys.stderr.write(f"❌ Could not open printer: {e}\n")
        # Return a dummy object with safe methods so the rest of the code can continue
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
# Helper: does this line contain the configured call sign?
# ----------------------------------------------------------------------
def contains_callsign(line: str, cfg: dict) -> bool:
    if not cfg["filter_enabled"] or not cfg["call_sign"]:
        return False
    return cfg["call_sign"] in line.upper()


# ----------------------------------------------------------------------
# Main loop – decode, rolling buffer, response detection, real‑time printing
# ----------------------------------------------------------------------
def main():
    cfg = load_config()
    if cfg["filter_enabled"]:
        print(f"🔧 Filter enabled – waiting for a response to "
              f"'{cfg['call_sign']}'.")
    else:
        print("🔧 Filter disabled – printing every decoded line.")

    printer = init_printer()
    decoder = start_rtl_fm()

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

            # Echo to console for debugging / vi