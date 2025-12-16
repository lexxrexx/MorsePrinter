# 📜 Morse‑to‑Receipt Printer

**Real‑time decoding of CW (Morse code) from an SDR and printing the conversation on a thermal receipt printer.**

* * *

## Table of Contents

1.  [Overview](#overview)
2.  [Hardware Requirements](#hardware-requirements)
3.  [Software Dependencies](#software-dependencies)
4.  [Installation Instructions](#installation-instructions)
5.  [Configuration File (`config.yaml`)](#configuration-file)
6.  [How It Works](#how-it-works)
7.  [Running the Program](#running-the-program)
8.  [Troubleshooting](#troubleshooting)
9.  [License & Credits](#license-credits)

* * *

## Overview

This project listens to a ham‑radio frequency with an **RTL‑SDR**, demodulates the signal, decodes Morse code, and prints the resulting conversation on a **thermal receipt printer** (ESC/POS compatible).

-   A 15‑second rolling buffer is always kept.
-   When a line containing the configured call‑sign is heard, the script *does not print it immediately*. It waits for a **response** – any line that does **not** contain the same call‑sign.
-   Upon the first response:
    1.  The rolling buffer (minus any lines that still contain the call‑sign) is flushed to the printer (lead‑in).
    2.  The response line is printed.
    3.  All subsequent lines are printed in real‑time until a QSO‑termination token (e.g., `73`, `SK`, `RR`, `DIT DIT`) is detected.

If the filter is disabled, every decoded line is printed immediately (original behaviour).

* * *

## Hardware Requirements

| Device | Purpose |
| --- | --- |
| USB RTL‑SDR dongle (e.g., NooElec NESDR) | Receives the RF carrier. |
| Thermal receipt printer (ESC/POS compatible, e.g., Epson TM‑T20II) | Prints the decoded conversation. |
| Ubuntu server (18.04 + recommended) | Runs the software stack. |

* * *

## Software Dependencies

| Category | Package | Install command |
| --- | --- | --- |
| SDR driver | rtl-sdr | `sudo apt-get install rtl-sdr` |
| Audio conversion | sox | `sudo apt-get install sox` |
| Morse decoder | multimon-ng | `sudo apt-get install multimon-ng` |
| Python runtime | python3, python3-pip | `sudo apt-get install python3 python3-pip` |
| ESC/POS driver | python-escpos (PyPI) | `pip3 install python-escpos` |
| YAML parser | pyyaml (PyPI) | `pip3 install pyyaml` |

* * *

## Installation Instructions

### Automatic install (via `install.sh`)

An `install.sh` script is included in the repository. It performs a one‑click setup:

```
# Download and run the installer in one step
curl -L https://github.com/lexxrexx/MorsePrinter/raw/main/install.sh | bash
```

The script will:

1.  Download the latest source archive from GitHub.
2.  Install all required `apt` packages.
3.  Install the required Python packages.
4.  Create a default `config.yaml` (if one does not exist).
5.  Make `morse_printer.py` executable.

### Manual install (step‑by‑step)

# 1 Update the system
```sudo apt-get update && sudo apt-get upgrade -y```

# 2 Install required system packages
```sudo apt-get install -y rtl-sdr sox multimon-ng python3 python3-pip unzip wget```

#  3 Install required Python packages
```pip3 install --upgrade pip
pip3 install python-escpos pyyaml```

# 4 Clone the repository (or download the zip)
```git clone https://github.com/lexxrexx/MorsePrinter.git
cd MorsePrinter```

# 5 Make the main script executable
```chmod +x morse_printer.py```

# 6 (Optional) Create a default config file if you don’t have one yet
```nano config.yaml
filter_enabled: true          # true → conversation mode, false → print every line
call_sign: "K1ABC"           # the call‑sign that must be responded to
```


## How It Works

Rolling buffer: Stores every decoded line with a timestamp for the last 15 seconds.
Call‑sign detection: When a line contains the configured call‑sign, the script sets awaiting_response = True and does not print.
Response detection: The next line that does not contain the call‑sign is treated as the response. At that moment:
    
        The rolling buffer (minus any lines still containing the call‑sign) is flushed to the printer (lead‑in).
        The response line is printed.
        The script enters printing_active = True and prints every subsequent line in real‑time.
    

Termination detection: When a line matches any token in the termination list (73, SK, RR, DIT DIT, …) the printer cuts the paper, the state resets, and the script returns to idle monitoring.
Filter disabled: If filter_enabled: false, the script skips all of the above logic and simply prints each line as it arrives.




## Running the Program

cd ~/MorsePrinter   # or wherever you placed the files
./morse_printer.py

You should see console output such as:
🔧 Filter enabled – waiting for a response to 'K1ABC'.
🛰️  Listening for Morse… Press Ctrl‑C to stop.
📡 Received: K1ABC CQ CQ DE K1ABC
📡 Received: K2XYZ DE K1ABC 599
📡 Received: K1ABC 73

The printer will receive the lead‑in (the 15 seconds before the response), then print the response and all following traffic until the 73 terminates the QSO.



## Troubleshooting

No output on the printerIncorrect USB IDs or missing permissions - Run lsusb to get the correct IDs, update the script, and ensure your user is in the lp group or run with sudo.
Script never detects a response - The call‑sign in config.yaml does not exactly match the transmitted call‑sign.Double‑check spelling and remove surrounding whitespace.
All lines are printed immediately (filter seems ignored) - filter_enabled is set to false or the config file isn’t being read. Confirm config.yaml is in the same directory and contains filter_enabled: true.
High CPU usageVery high sample rate or noisy signal. Lower the gain or sample rate in the script (variables GAIN and the -s argument to rtl_fm).





## License & Credits

License: MIT – feel free to modify, redistribute, or incorporate into larger projects.
Core libraries:
    
        rtl_sdr – Osmocom Project
        sox – SoX Team
        multimon-ng – Multi‑Mode Decoder project
        python-escpos – Daniel R. (GitHub)
        pyyaml – Python YAML parser