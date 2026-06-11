#!/bin/bash
# ============================================
#  TTC-Map - One-click setup (macOS)
#  Installs Python + Node deps, configures
#  env.config, and runs the first data sync.
#  Double-click in Finder or run: ./setup.command
# ============================================
set -e
cd "$(dirname "$0")"

bash Setup/Setup.sh

echo ""
echo "📦 Running first data sync..."
echo "   (downloads the ~66 MB TTC GTFS feed and builds the database — takes a few minutes)"
cd node-api
npm run sync

echo ""
echo "═══════════════════════════════════════════"
echo "  ✅  Setup complete! Run start.command to launch."
echo "═══════════════════════════════════════════"
