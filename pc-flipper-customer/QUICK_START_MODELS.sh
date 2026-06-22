#!/bin/bash
# Quick start guide for downloading models

echo "================================================================================"
echo "                FlipFlop 3D Models - Quick Start Guide"
echo "================================================================================"
echo ""
echo "This will help you download real 3D models from Sketchfab."
echo ""

# Run Python script if available
if command -v python3 &> /dev/null; then
  python3 download-models.py
else
  echo "Python3 not found. Please install Python 3.6+ to continue."
  exit 1
fi
