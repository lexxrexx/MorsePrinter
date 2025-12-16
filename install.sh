#!/usr/bin/env bash
# ------------------------------------------------------------
# One‑click installer for the Morse‑to‑Receipt Printer project
# ------------------------------------------------------------


set -euo pipefail

# ---------- Helper functions ----------
log()   { echo -e "\e[32m[INFO]\e[0m $*"; }
error() { echo -e "\e[31m[ERROR]\e[0m $*" >&2; exit 1; }

# ---------- Variables ----------
REPO_URL="https://github.com/lexxrexx/MorsePrinter"
ZIP_URL="${REPO_URL}/archive/refs/heads/main.zip"
PROJECT_DIR="${HOME}/morse-printer"
TMP_ZIP="/tmp/morse-printer.zip"

# ---------- 1️⃣ Download the repository ----------
log "Downloading latest source archive..."
curl -L -sSf "${ZIP_URL}" -o "${TMP_ZIP}" || error "Failed to download archive."

log "Extracting archive..."
unzip -q -o "${TMP_ZIP}" -d "${HOME}" || error "Failed to unzip archive."
rm -f "${TMP_ZIP}"

# The zip extracts to a folder named MorsePrinter‑main; rename it
EXTRACTED_DIR=$(find "${HOME}" -maxdepth 1 -type d -name "MorsePrinter-*" | head -n1)
[[ -n "${EXTRACTED_DIR}" ]] || error "Could not locate extracted directory."
mv -f "${EXTRACTED_DIR}" "${PROJECT_DIR}" || error "Failed to move project."

# ---------- 2️⃣ Install system packages ----------
log "Updating package index..."
sudo apt-get update -y || error "apt-get update failed."

log "Installing required apt packages..."
sudo apt-get install -y \
    rtl-sdr \
    sox \
    multimon-ng \
    python3 \
    python3-pip \
    unzip \
    wget \
    > /dev/null || error "Failed to install apt packages."

# ---------- 3️⃣ Install Python packages ----------
log "Installing required Python packages (system‑wide)..."
# NOTE: We deliberately **do not** run `pip install --upgrade pip` here.
python3 -m pip install --quiet \
    python-escpos \
    pyyaml \
    > /dev/null || error "Failed to install Python packages."

# ---------- 4️⃣ Final touches ----------
log "Making the main script executable..."
chmod +x "${PROJECT_DIR}/morse_printer.py" || error "chmod failed."

CONFIG_FILE="${PROJECT_DIR}/config.yaml"
if [[ ! -f "${CONFIG_FILE}" ]]; then
    cat > "${CONFIG_FILE}" <<EOF
filter_enabled: true          # true → conversation mode, false → print every line
call_sign: "K1ABC"           # the call‑sign that must be responded to
EOF
    log "Created default config file at ${CONFIG_FILE}"
else
    log "Config file already exists at ${CONFIG_FILE}"
fi

log "Installation complete! 🎉"
log "To start the program:"
echo -e "\n    cd \"${PROJECT_DIR}\"\n    ./morse_printer.py\n"
log "Edit ${CONFIG_FILE} if you need to change the call‑sign or disable the filter."