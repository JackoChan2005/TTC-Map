#!/bin/bash
set -e

# ─────────────────────────────────────────────
# TTC-Map — Full Environment Setup
# Run from the project root:  bash setup.sh
# ─────────────────────────────────────────────

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
echo "📂 Project root: $PROJECT_ROOT"

# ── 1. Fix requirements.txt encoding (UTF-16 → UTF-8) ──
echo ""
echo "🔧 Fixing requirements.txt encoding..."
if file "$PROJECT_ROOT/requirements.txt" | grep -qi "utf-16\|bom"; then
    iconv -f UTF-16 -t UTF-8 "$PROJECT_ROOT/requirements.txt" \
        | sed 's/\r//g' | grep -v '^\s*$' > "$PROJECT_ROOT/requirements_fixed.txt"
    mv "$PROJECT_ROOT/requirements_fixed.txt" "$PROJECT_ROOT/requirements.txt"
    echo "   ✅ Converted to UTF-8"
else
    echo "   ✅ Already UTF-8, no conversion needed"
fi

# ── 2. Python virtual environment ──
echo ""
echo "🐍 Setting up Python virtual environment..."
if [ ! -d "$PROJECT_ROOT/venv" ]; then
    python3 -m venv "$PROJECT_ROOT/venv"
    echo "   ✅ venv created"
else
    echo "   ✅ venv already exists"
fi

echo "📦 Upgrading pip and installing pipreqs..."
"$PROJECT_ROOT/venv/bin/pip" install --upgrade pip
"$PROJECT_ROOT/venv/bin/pip" install pipreqs

echo "🔍 Scanning Python files for imports with pipreqs..."
"$PROJECT_ROOT/venv/bin/pipreqs" "$PROJECT_ROOT/API" --force --savepath "$PROJECT_ROOT/requirements.txt"
echo "   ✅ requirements.txt updated from source scan:"
cat "$PROJECT_ROOT/requirements.txt"

echo ""
echo "📦 Installing Python dependencies..."
"$PROJECT_ROOT/venv/bin/pip" install -r "$PROJECT_ROOT/requirements.txt"
echo "   ✅ Python packages installed"

# ── 3. Node.js dependencies ──
echo ""
echo "📦 Installing Node.js dependencies..."
cd "$PROJECT_ROOT/node-api"
npm install
echo "   ✅ Node packages installed"

# ── 4. Summary ──
echo ""
echo "═══════════════════════════════════════════"
echo "  ✅  Setup complete!"
echo "═══════════════════════════════════════════"
echo ""
echo "  PYTHON API (FastAPI):"
echo "    Activate venv:   source venv/bin/activate"
echo "    Init DB:         cd API/src && python update_db.py"
echo "    Run server:      fastapi dev API/src/main.py"
echo ""
echo "  NODE API (Express):"
echo "    Start server:    cd node-api && npm start"
echo "    Dev mode:        cd node-api && npm run dev"
echo "    Frontend:        http://localhost:3000"
echo ""
echo "═══════════════════════════════════════════"
echo ""
echo "  Python dependencies found in source files:"
echo "    fastapi, sqlalchemy, pandas, requests"
echo ""
echo "  Node dependencies (from package.json):"
echo "    express, sqlite3, dotenv, nodemon (dev)"
echo ""
echo "  JS source files with NO require/import:"
echo "    node-api/src/sync/transform.js"
echo "    node-api/public/app.js (browser script, uses fetch)"
echo "═══════════════════════════════════════════"