 Morse‑to‑Receipt Printer – README body {font-family:Arial,Helvetica,sans-serif; max-width:900px; margin:2rem auto; line-height:1.6; color:#333; background:#fafafa; padding:0 1rem;} h1, h2, h3 {color:#2c3e50;} pre {background:#f4f4f4; border:1px solid #ddd; padding:1rem; overflow:auto;} code {font-family:"Courier New",Courier,monospace;} ul, ol {margin-left:1.5rem;} hr {border:none; border-top:1px solid #ddd; margin:2rem 0;}

# 📜 Morse‑to‑Receipt Printer

**Real‑time decoding of CW (Morse code) from an SDR and printing the conversation on a thermal receipt printer.**

***

## Table of Contents

1.  [Overview](#overview)
2.  [Hardware Requirements](#hardware-requirements)
3.  [Software Dependencies](#software-dependencies)
4.  [Installation Steps](#installation-steps)
5.  [Configuration File (`config.yaml`)](#configuration-file)
6.  [How It Works](#how-it-works)
7.  [Running the Program](#running-the-program)
8.  [Troubleshooting](#troubleshooting)
9.  [License & Credits](#license--credits)

***

## Overview

This project listens to a ham‑radio frequency with an **RTL‑SDR**, demodulates the signal, decodes Morse code, and prints the resulting conversation on a **thermal receipt printer** (ESC/POS compatible).

*   A **15‑second rolling buffer** is always maintained.
*   When a line containing the **configured call‑sign** is heard, the script _does not print it immediately_. It waits for a **response** – any line that does **not** contain the same call‑sign.
*   As soon as the first response arrives:
    1.  The rolling buffer (minus any lines that contain the call‑sign) is flushed to the printer – this provides the “lead‑in”.
    2.  The response line itself is printed.
    3.  From that point onward every decoded line is printed **in real‑time** until a QSO‑termination token (e.g., `73`, `SK`, `RR`, `DIT DIT`) is detected.

If the filter is disabled, the script behaves like the original version and prints each decoded line as soon as it arrives.

***

## Hardware Requirements

| Device | Why |
| --- | --- |
| USB RTL‑SDR dongle (e.g., NooElec NESDR) | Receives the RF carrier. |
| Thermal receipt printer (ESC/POS compatible, e.g., Epson TM‑T20II) | Prints the decoded conversation. |
| Ubuntu server (18.04 + recommended) | Runs the software stack. |

***

## Software Dependencies

| Category | Package | Install command |
| --- | --- | --- |
| SDR driver | rtl-sdr | `sudo apt-get install rtl-sdr` |
| Audio conversion | sox | `sudo apt-get install sox` |
| Morse decoder | multimon-ng | `sudo apt-get install multimon-ng` |
| Python runtime | python3, python3-pip | `sudo apt-get install python3 python3-pip` |
| ESC/POS driver | python-escpos (PyPI) | `pip3 install python-escpos` |
| YAML parser (optional, only needed for the config file) | pyyaml | `pip3 install pyyaml` |

***

## Installation Steps

1.  **Update the system**
    
    ```
    sudo apt-get update && sudo apt-get upgrade -y
    ```
    
2.  **Install required system packages**
    
    ```
    sudo apt-get install -y rtl-sdr sox multimon-ng python3 python3-pip
    ```
    
3.  **Install Python libraries**
    
    ```
    pip3 install python-escpos pyyaml
    ```
    
4.  **Copy the script**
    
    ```
    mkdir -p ~/morse-printer && cd ~/morse-printer
    # Save the Python script (shown below) as morse_printer.py
    chmod +x morse_printer.py
    ```
    
5.  **Create the configuration file** (see next section).

***

## Configuration File (`config.yaml`)

Place a file named `config.yaml` in the same directory as `morse_printer.py`. Example:

```
# config.yaml
filter_enabled: true          # true → conversation‑mode, false → print every line
call_sign: "K1ABC"           # the call‑sign that must be responded to
```

**Fields**

*   `filter_enabled` (boolean) – When `true` the script uses the rolling‑buffer / response logic described above. When `false` it prints each decoded line immediately (original behaviour).
*   `call_sign` (string) – The exact call‑sign (case‑insensitive) that triggers the “wait‑for‑response” state. If the field is empty or omitted, the script behaves as if `filter_enabled` were `false`.

***

## How It Works (Step‑by‑Step)

1.  **Rolling buffer**: The script stores every decoded line together with a timestamp for the last 15 seconds.
2.  **Call‑sign detection**: When a line contains the configured call‑sign, the script sets `awaiting_response = True` and does \*\*not\*\* print anything.
3.  **Response detection**: The next line that _does not_ contain the call‑sign is considered the response. At that moment:
    *   The rolling buffer is flushed to the printer, but any lines that still contain the call‑sign are removed (so the initial call‑sign isn’t printed).
    *   The response line itself is printed.
    *   The script enters `printing_active = True` and starts printing every subsequent line in real‑time.
4.  **Termination**: When a line matches any token in the termination list (`73`, `SK`, `RR`, `DIT DIT`, …) the printer cuts the paper, the state variables are reset, and the script returns to idle monitoring.
5.  **Filter disabled**: If `filter_enabled: false`, the script skips all of the above logic and simply prints each line as it arrives.

***

## Running the Program

```
cd ~/morse-printer
./morse_printer.py
```

You should see console output like:

```
🔧 Filter enabled – waiting for a response to 'K1ABC'.
🛰️  Listening for Morse… Press Ctrl‑C to stop.
📡 Received: K1ABC CQ CQ DE K1ABC
📡 Received: K2XYZ DE K1ABC 599
📡 Received: K1ABC 73
```

The printer will receive the lead‑in (the 15 seconds before the response), then print the response and all following traffic until the `73` terminates the QSO.

***

## Troubleshooting

| Problem | Possible Cause | Solution |
| --- | --- | --- |
| No output on the printer | Incorrect USB vendor/product IDs or missing permissions. | Run `lsusb` to get the correct IDs, update `PRINTER_VENDOR_ID`/`PRINTER_PRODUCT_ID` in the script, and ensure your user is in the `lp` group or run with `sudo`. |
| Script never detects a response | The call‑sign in `config.yaml` does not exactly match the transmitted call‑sign (case‑insensitive but must be the same characters). | Double‑check the call‑sign spelling and remove any surrounding whitespace. |
| All lines are printed immediately (filter seems ignored) | `filter_enabled` is set to `false` or the config file isn’t being read. | Confirm `config.yaml` is in the same directory as the script and contains `filter_enabled: true`. |
| High CPU usage | Very high sample rate or noisy signal. | Try lowering the gain or sample rate in the script (variables `GAIN` and the `-s` argument to `rtl_fm`). |

***

## License & Credits

*   **License:** MIT – feel free to modify, redistribute, or incorporate into larger projects.
*   **Core libraries:**
    *   rtl\_sdr – Osmocom Project
    *   sox – SoX Team
    *   multimon-ng – Multi‑Mode Decoder project
    *   python-escpos – Daniel R. (GitHub)
    *   pyyaml – Python YAML parser

***
