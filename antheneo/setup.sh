#!/usr/bin/env bash
# Antheneo Browser — Setup Script
set -e

echo "╔══════════════════════════════════════╗"
echo "║    Antheneo Browser — Setup          ║"
echo "╚══════════════════════════════════════╝"

# Check Python
if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 is required"
    exit 1
fi

PYTHON=$(command -v python3)
echo "Using Python: $PYTHON ($($PYTHON --version))"

# Create virtual environment
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    $PYTHON -m venv .venv
fi

# Activate
source .venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install --upgrade pip -q
pip install -r requirements.txt

# Install optional system tools (whois for recon tab)
if command -v apt-get &>/dev/null; then
    echo "Installing optional system tools..."
    sudo apt-get install -y whois 2>/dev/null || true
elif command -v brew &>/dev/null; then
    brew install whois 2>/dev/null || true
fi

echo ""
echo "✔ Setup complete!"
echo ""
echo "Run Antheneo with:"
echo "  source .venv/bin/activate && python browser.py"
