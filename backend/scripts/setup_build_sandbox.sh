#!/usr/bin/env bash
# Sets up backend/build_sandbox/node_modules and stubs better-sqlite3.
# Run once after clone, or with --force to rebuild.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SANDBOX_DIR="$(cd "$SCRIPT_DIR/../build_sandbox" && pwd)"
STUB_DIR="$SANDBOX_DIR/node_modules/better-sqlite3"
STUB_FILE="$STUB_DIR/lib/index.js"
STUB_MARKER="$STUB_DIR/.aegis-stubbed"

FORCE=0
if [ "${1:-}" = "--force" ]; then FORCE=1; fi

cd "$SANDBOX_DIR"

# 1. Install (or reinstall) deps
if [ ! -d "node_modules" ] || [ "$FORCE" -eq 1 ]; then
  echo "[setup] Installing sandbox dependencies in $SANDBOX_DIR ..."
  rm -rf node_modules
  npm install --ignore-scripts --no-audit --no-fund
else
  echo "[setup] node_modules already present (pass --force to rebuild)."
fi

# 2. Stub better-sqlite3
if [ ! -d "$STUB_DIR" ]; then
  echo "[setup] ERROR: $STUB_DIR not found after npm install. Aborting." >&2
  exit 1
fi

if [ -f "$STUB_MARKER" ] && [ "$FORCE" -eq 0 ]; then
  echo "[setup] better-sqlite3 already stubbed."
else
  echo "[setup] Stubbing better-sqlite3 at $STUB_FILE ..."
  mkdir -p "$(dirname "$STUB_FILE")"
  cat > "$STUB_FILE" <<'STUB_EOF'
// Aegis stub of better-sqlite3 — used ONLY during build verification.
// The real package is reinstalled fresh in customer deployments.
'use strict';
class Statement {
  run() { return { changes: 0, lastInsertRowid: 0 }; }
  get() { return undefined; }
  all() { return []; }
  iterate() { return [][Symbol.iterator](); }
  pluck() { return this; }
  expand() { return this; }
  raw() { return this; }
  bind() { return this; }
  columns() { return []; }
  safeIntegers() { return this; }
}
class Database {
  constructor(path, opts) {
    this.open = true;
    this.inTransaction = false;
    this.name = path || ':memory:';
    this.memory = false;
    this.readonly = (opts && opts.readonly) || false;
  }
  prepare() { return new Statement(); }
  exec() { return this; }
  pragma() { return []; }
  transaction(fn) { return fn; }
  close() { this.open = false; }
  function() { return this; }
  aggregate() { return this; }
  loadExtension() { return this; }
  defaultSafeIntegers() { return this; }
  unsafeMode() { return this; }
  serialize() { return Buffer.alloc(0); }
}
module.exports = Database;
module.exports.default = Database;
STUB_EOF
  touch "$STUB_MARKER"
fi

echo "[setup] Done. Sandbox ready at $SANDBOX_DIR"
