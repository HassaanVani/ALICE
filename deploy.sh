#!/usr/bin/env bash
#
# ALICE Deploy Script
# Usage: ./deploy.sh [command] [options]
#
# Commands:
#   setup       Install Python venv + npm deps (run once)
#   start       Launch backend + dashboard (default)
#   backend     Launch only the Python backend
#   dashboard   Launch only the dashboard dev server
#   stop        Kill all running ALICE processes
#   status      Show what's running
#   logs        Tail all log files
#
# Options (for start/backend):
#   --mode MODE     idle|auto_sort|auto_tetris|demo|calibrate|puppeteer (default: idle)
#   --hardware      Disable simulate mode (connect to real hardware)
#   --record        Enable session recording
#   --replay FILE   Replay a recorded session
#
# Examples:
#   ./deploy.sh setup              # first-time setup
#   ./deploy.sh                    # start everything in simulate mode
#   ./deploy.sh start --mode demo  # start with demo mode
#   ./deploy.sh dashboard          # just the UI
#   ./deploy.sh stop               # shut it all down

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$ROOT_DIR/venv"
DASHBOARD_DIR="$ROOT_DIR/dashboard"
LOG_DIR="$ROOT_DIR/.logs"
PID_DIR="$ROOT_DIR/.pids"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
DIM='\033[2m'
BOLD='\033[1m'
NC='\033[0m'

log()  { echo -e "${BLUE}[ALICE]${NC} $*"; }
ok()   { echo -e "${GREEN}  [OK]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
err()  { echo -e "${RED} [ERR]${NC} $*"; }

# ─── Helpers ───

ensure_dirs() {
  mkdir -p "$LOG_DIR" "$PID_DIR"
}

activate_venv() {
  if [ -f "$VENV_DIR/bin/activate" ]; then
    source "$VENV_DIR/bin/activate"
  else
    err "No venv found. Run: ./deploy.sh setup"
    exit 1
  fi
}

save_pid() {
  echo "$2" > "$PID_DIR/$1.pid"
}

read_pid() {
  local f="$PID_DIR/$1.pid"
  [ -f "$f" ] && cat "$f" || echo ""
}

is_running() {
  local pid
  pid=$(read_pid "$1")
  [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null
}

kill_proc() {
  local pid
  pid=$(read_pid "$1")
  if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null || true
    # Wait briefly then force-kill if still alive
    for _ in 1 2 3; do
      kill -0 "$pid" 2>/dev/null || break
      sleep 0.5
    done
    kill -0 "$pid" 2>/dev/null && kill -9 "$pid" 2>/dev/null || true
    ok "Stopped $1 (pid $pid)"
  fi
  rm -f "$PID_DIR/$1.pid"
}

wait_for_log() {
  local logfile=$1 pattern=$2 name=$3 timeout=${4:-15}
  local elapsed=0
  while ! grep -q "$pattern" "$logfile" 2>/dev/null; do
    # Check if the process died
    sleep 0.5
    elapsed=$((elapsed + 1))
    if [ "$elapsed" -ge "$((timeout * 2))" ]; then
      warn "$name did not start within ${timeout}s"
      if [ -f "$logfile" ]; then
        echo -e "  ${DIM}Last log lines:${NC}"
        tail -5 "$logfile" 2>/dev/null | sed "s/^/    /"
      fi
      return 1
    fi
  done
  ok "$name ready"
}

check_port() {
  nc -z localhost "$1" 2>/dev/null
}

# ─── Commands ───

cmd_setup() {
  log "Setting up ALICE development environment..."
  echo

  # Python venv
  if [ ! -f "$VENV_DIR/bin/activate" ]; then
    log "Creating Python virtual environment..."
    python3 -m venv "$VENV_DIR"
    ok "venv created at $VENV_DIR"
  else
    ok "venv already exists"
  fi

  source "$VENV_DIR/bin/activate"

  log "Installing Python dependencies..."
  pip install --upgrade pip -q
  pip install -r "$ROOT_DIR/requirements.txt" -q
  ok "Python deps installed"

  # Node/Dashboard
  if [ -d "$DASHBOARD_DIR" ]; then
    log "Installing dashboard dependencies..."
    (cd "$DASHBOARD_DIR" && npm install --silent)
    ok "Dashboard deps installed"
  fi

  echo
  ok "Setup complete. Run ${BOLD}./deploy.sh${NC} to start."
}

cmd_start() {
  ensure_dirs

  local mode="idle"
  local simulate="--simulate"
  local extra_args=()

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --mode)      mode="$2"; shift 2 ;;
      --hardware)  simulate=""; shift ;;
      --record)    extra_args+=("--record"); shift ;;
      --replay)    extra_args+=("--replay" "$2"); shift 2 ;;
      *)           extra_args+=("$1"); shift ;;
    esac
  done

  # Check for already-running processes
  if is_running backend || is_running dashboard; then
    warn "ALICE processes already running. Run ./deploy.sh stop first."
    cmd_status
    exit 1
  fi

  echo
  echo -e "${CYAN}${BOLD}  ╔═══════════════════════════════════╗${NC}"
  echo -e "${CYAN}${BOLD}  ║         A.L.I.C.E. Deploy         ║${NC}"
  echo -e "${CYAN}${BOLD}  ╚═══════════════════════════════════╝${NC}"
  echo
  echo -e "  ${DIM}Mode:${NC}      ${BOLD}$mode${NC}"
  echo -e "  ${DIM}Simulate:${NC}  ${BOLD}${simulate:+yes}${simulate:-no (hardware)}${NC}"
  echo

  # Start backend
  start_backend "$mode" "$simulate" "${extra_args[@]+"${extra_args[@]}"}"

  # Start dashboard
  start_dashboard

  echo
  echo -e "${GREEN}${BOLD}  All services running.${NC}"
  echo
  echo -e "  ${DIM}Dashboard:${NC}    ${BOLD}http://localhost:3001${NC}"
  echo -e "  ${DIM}Audience:${NC}     ${BOLD}http://localhost:3001/#/audience${NC}"
  echo -e "  ${DIM}Tensor WS:${NC}    ${DIM}ws://localhost:8765${NC}"
  echo -e "  ${DIM}Puppet WS:${NC}    ${DIM}ws://localhost:8766${NC}"
  echo -e "  ${DIM}Audience WS:${NC}  ${DIM}ws://localhost:8767${NC}"
  echo
  echo -e "  ${DIM}Logs:${NC}         ${DIM}$LOG_DIR/${NC}"
  echo -e "  ${DIM}Stop:${NC}         ${BOLD}./deploy.sh stop${NC}"
  echo
}

start_backend() {
  local mode="$1" simulate="$2"
  shift 2

  activate_venv
  log "Starting backend (mode=$mode)..."

  local cmd=(python "$ROOT_DIR/main.py" --mode "$mode")
  [ -n "$simulate" ] && cmd+=("$simulate")
  [ $# -gt 0 ] && cmd+=("$@")

  > "$LOG_DIR/backend.log"  # truncate old log
  "${cmd[@]}" >> "$LOG_DIR/backend.log" 2>&1 &
  save_pid backend $!

  # Wait for tensor server startup message in log
  wait_for_log "$LOG_DIR/backend.log" "Tensor stream server started" "Backend" 20 || true
}

start_dashboard() {
  if [ ! -d "$DASHBOARD_DIR/node_modules" ]; then
    warn "Dashboard node_modules missing. Running npm install..."
    (cd "$DASHBOARD_DIR" && npm install --silent)
  fi

  log "Starting dashboard..."
  > "$LOG_DIR/dashboard.log"
  (cd "$DASHBOARD_DIR" && npx vite --port 3001) >> "$LOG_DIR/dashboard.log" 2>&1 &
  save_pid dashboard $!

  wait_for_log "$LOG_DIR/dashboard.log" "Local:" "Dashboard" 15 || true
}

cmd_backend() {
  ensure_dirs

  local mode="idle"
  local simulate="--simulate"
  local extra_args=()

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --mode)      mode="$2"; shift 2 ;;
      --hardware)  simulate=""; shift ;;
      --record)    extra_args+=("--record"); shift ;;
      --replay)    extra_args+=("--replay" "$2"); shift 2 ;;
      *)           extra_args+=("$1"); shift ;;
    esac
  done

  if is_running backend; then
    warn "Backend already running."
    cmd_status
    exit 1
  fi

  start_backend "$mode" "$simulate" "${extra_args[@]+"${extra_args[@]}"}"
  ok "Backend started. Logs: $LOG_DIR/backend.log"
}

cmd_dashboard() {
  ensure_dirs

  if is_running dashboard; then
    warn "Dashboard already running."
    cmd_status
    exit 1
  fi

  start_dashboard
  ok "Dashboard started at http://localhost:3001"
}

cmd_stop() {
  log "Stopping ALICE..."
  kill_proc dashboard
  kill_proc backend
  ok "All stopped."
}

cmd_status() {
  echo
  echo -e "${BOLD}ALICE Process Status${NC}"
  echo -e "${DIM}────────────────────────────────${NC}"

  for proc in backend dashboard; do
    local pid
    pid=$(read_pid "$proc")
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
      echo -e "  ${GREEN}●${NC} ${BOLD}$proc${NC}  ${DIM}pid=$pid${NC}"
    else
      echo -e "  ${DIM}○${NC} ${DIM}$proc${NC}  ${DIM}not running${NC}"
      rm -f "$PID_DIR/$proc.pid"
    fi
  done

  echo -e "${DIM}────────────────────────────────${NC}"

  # Port check
  for port_info in "8765:Tensor WS" "8766:Puppet WS" "8767:Audience WS" "3001:Dashboard"; do
    local port="${port_info%%:*}" name="${port_info##*:}"
    if check_port "$port"; then
      echo -e "  ${GREEN}●${NC} :$port  $name"
    else
      echo -e "  ${DIM}○${NC} ${DIM}:$port  $name${NC}"
    fi
  done
  echo
}

cmd_logs() {
  ensure_dirs
  log "Tailing logs (Ctrl+C to stop)..."
  echo
  tail -f "$LOG_DIR"/*.log 2>/dev/null || warn "No log files yet. Start services first."
}

# ─── Main ───

cmd="${1:-start}"
shift 2>/dev/null || true

case "$cmd" in
  setup)     cmd_setup ;;
  start)     cmd_start "$@" ;;
  backend)   cmd_backend "$@" ;;
  dashboard) cmd_dashboard ;;
  stop)      cmd_stop ;;
  status)    cmd_status ;;
  logs)      cmd_logs ;;
  -h|--help|help)
    # Print the header comment block as help
    sed -n '2,/^$/p' "${BASH_SOURCE[0]}" | sed 's/^# \?//'
    ;;
  *)
    err "Unknown command: $cmd"
    echo "Run ./deploy.sh help for usage."
    exit 1
    ;;
esac
