#!/usr/bin/env bash
# ------------------------------------------------------------
# One‑click installer for the Morse‑to‑Receipt Printer project
# ------------------------------------------------------------
# 1️⃣ Download the latest source from GitHub
# 2️⃣ Install all required system packages (apt)
# 3️⃣ Install required Python packages (pip)
# 4️⃣ Set up the project directory and make the script executable
# ------------------------------------------------------------

# Exit immediately on any error and treat unset variables as errors
set -euo pipefail

# ------------------------------------------------------------
# Helper functions
# ------------------------------------------------------------
log()   { echo -e "\e[32m[INFO]\e[0m $*"; }
error() { echo -e "\e[31m[ERROR]\e[0m $*" >&2; exit 1; }

# Trap any command that exits non‑zero and report it
trap 'error "An unexpected error occurred at line $LINENO. Installation halted."' ERR

# ------------------------------------------------------------
# Variables (now pointing at your actual repo)
# ------------------------------------------------------------
REPO_URL="https://github.com/lexxrexx/MorsePrinter"
ZIP_URL="${REPO_URL}/archive/refs/heads/main.zip"
PROJECT_DIR="${HOME}/morse-printer"
TMP_ZIP="/tmp/morse-printer.zip"

# ------------------------------------------------------------
# Download the repository
# ------------------------------------------------------------
log "Downloading latest source archive..."
curl -L -sSf "${ZIP_URL}" -o "${TMP_ZIP}" || error "Failed to download archive from ${ZIP_URL}."

log "Extracting archive..."
unzip -q -o "${TMP_ZIP}" -d "${HOME}" || error "Failed to unzip the downloaded archive."
rm -f "${TMP_ZIP}"

# The zip extracts to a folder named <repo>-main; rename it to a stable name
EXTRACTED_DIR=$(find "${HOME}" -maxdepth 1 -type d -name "MorsePrinter-*" | head -n1)
[[ -n "${EXTRACTED_DIR}" ]] || error "Could not locate extracted directory."
mv -f "${EXTRACTED_DIR}" "${PROJECT_DIR}" || error "Failed to move project to ${PROJECT_DIR}."

# ------------------------------------------------------------
# Install system dependencies
# ------------------------------------------------------------
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
    > /dev/null || error "Failed to install required apt packages."

# ------------------------------------------------------------
# Install Python dependencies
# ------------------------------------------------------------
log "Upgrading pip..."
python3 -m pip install --upgrade pip > /dev/null || error "Failed to upgrade pip."

log "Installing required Python packages..."
python3 -m pip install --quiet \
    python-escpos \
    pyyaml \
    > /dev/null || error "Failed to install required Python packages."

# ------------------------------------------------------------
# Make the script executable
# ------------------------------------------------------------
log "Setting execute permission on the main script..."
chmod +x "${PROJECT_DIR}/morse_printer.py" || error "Failed to chmod the script."

# ------------------------------------------------------------
# Create a default config file (if missing)
# ------------------------------------------------------------
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

# ------------------------------------------------------------
# Completion message
# ------------------------------------------------------------
log "Installation complete! 🎉"
log "To start the program, run:"
echo -e "\n    cd \"${PROJECT_DIR}\"\n    ./morse_printer.py\n"
log "Edit ${CONFIG_FILE} if you need to change the call‑sign or disable the filter."