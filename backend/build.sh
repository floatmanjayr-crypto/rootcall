#!/bin/bash
set -e # Stop script if any error occurs

echo "Current Python location: $(which python)"
echo "Current Pip version: $(pip --version)"

echo "Step 1: Upgrading Pip..."
python -m pip install --upgrade pip setuptools wheel

echo "New Pip version: $(pip --version)"

echo "Step 2: Installing Dependencies..."
# We explicitly install requirements
python -m pip install -r requirements.txt

echo "Build Complete!"
