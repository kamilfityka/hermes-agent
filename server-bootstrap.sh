#!/usr/bin/env bash
# ============================================================================
# Hermes Agent — one-shot server bootstrap
# ============================================================================
# Stands up Hermes on a fresh server in a single interactive run:
#
#   1. Pick a deployment mode          (native venv + systemd  |  Docker Compose)
#   2. Install dependencies            (delegates to ./setup-hermes.sh | docker build)
#   3. Choose an AI provider           (menu built dynamically from .env.example)
#   4. Enter the provider API key(s)   (written to ~/.hermes/.env, chmod 600)
#   5. (optional) Google Workspace OAuth  (Gmail / Calendar / Drive)
#   6. (optional) extra tool keys      (web search, Telegram, GitHub)
#   7. Start the agent                 (systemd service | foreground | docker up)
#
# Everything lands in $HERMES_HOME (default ~/.hermes) — the single source of
# truth for both the native and Docker deployments (it is the /opt/data volume
# inside the container), so switching between the two keeps your config.
#
# Usage:
#   ./server-bootstrap.sh              # interactive
#   ./server-bootstrap.sh --help
#
# The menus are interactive, so run this over an SSH session with a TTY.
# ============================================================================

set -euo pipefail

# ----------------------------------------------------------------------------
# Presentation helpers
# ----------------------------------------------------------------------------
if [ -t 1 ]; then
    GREEN='\033[0;32m'; YELLOW='\033[0;33m'; CYAN='\033[0;36m'
    RED='\033[0;31m'; BOLD='\033[1m'; DIM='\033[2m'; NC='\033[0m'
else
    GREEN=''; YELLOW=''; CYAN=''; RED=''; BOLD=''; DIM=''; NC=''
fi

log()  { printf '%b→%b %s\n'  "$CYAN"   "$NC" "$*"; }
ok()   { printf '%b✓%b %s\n'  "$GREEN"  "$NC" "$*"; }
warn() { printf '%b⚠%b %s\n'  "$YELLOW" "$NC" "$*"; }
err()  { printf '%b✗%b %s\n'  "$RED"    "$NC" "$*" >&2; }
hdr()  { printf '\n%b◆ %s%b\n' "${CYAN}${BOLD}" "$*" "$NC"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
ENV_FILE="$HERMES_HOME/.env"

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
    sed -n '3,23p' "$0" | sed 's/^# \{0,1\}//'
    exit 0
fi

require_tty() {
    if [ ! -t 0 ]; then
        err "This bootstrap is interactive and needs a terminal (stdin is not a TTY)."
        err "Run it directly over SSH, e.g.  ssh user@server -t '/path/to/server-bootstrap.sh'"
        exit 1
    fi
}

# ask "Question" "default"  -> echoes the answer (default if empty)
ask() {
    local q="$1" def="${2:-}" ans
    if [ -n "$def" ]; then
        read -r -p "$(printf '%b%s [%s]: %b' "$YELLOW" "$q" "$def" "$NC")" ans
    else
        read -r -p "$(printf '%b%s: %b' "$YELLOW" "$q" "$NC")" ans
    fi
    printf '%s' "${ans:-$def}"
}

# ask_secret "Prompt"  -> echoes the secret without echoing keystrokes
ask_secret() {
    local q="$1" ans
    read -r -s -p "$(printf '%b%s: %b' "$YELLOW" "$q" "$NC")" ans
    printf '\n' >&2
    printf '%s' "$ans"
}

# yesno "Question" "Y|N"  -> returns 0 for yes, 1 for no
yesno() {
    local q="$1" def="${2:-N}" ans hint
    [ "$def" = "Y" ] && hint="Y/n" || hint="y/N"
    read -r -p "$(printf '%b%s [%s]: %b' "$YELLOW" "$q" "$hint" "$NC")" ans
    ans="${ans:-$def}"
    case "$ans" in [Yy]*) return 0;; *) return 1;; esac
}

# ----------------------------------------------------------------------------
# ~/.hermes/.env upsert (KEY=VALUE), keeping the file owner-only readable.
# ----------------------------------------------------------------------------
set_env_kv() {
    local key="$1" val="$2"
    mkdir -p "$HERMES_HOME"
    touch "$ENV_FILE"
    chmod 600 "$ENV_FILE" 2>/dev/null || true
    # Drop any existing definition (commented or live) then append the new one.
    if grep -qE "^[#[:space:]]*${key}=" "$ENV_FILE" 2>/dev/null; then
        grep -vE "^[#[:space:]]*${key}=" "$ENV_FILE" > "$ENV_FILE.tmp" || true
        mv "$ENV_FILE.tmp" "$ENV_FILE"
    fi
    printf '%s=%s\n' "$key" "$val" >> "$ENV_FILE"
    chmod 600 "$ENV_FILE" 2>/dev/null || true
}

# ----------------------------------------------------------------------------
# Provider catalogue — parsed live from .env.example so the menu never goes
# stale: any `# LLM PROVIDER (Name)` block that documents a `*_API_KEY` /
# `*_TOKEN` line is picked up automatically.
# ----------------------------------------------------------------------------
PROV_NAME=(); PROV_KEY=(); PROV_URL=()

load_providers() {
    local parsed
    parsed="$(awk '
        /LLM PROVIDER \(/ {
            name=$0; sub(/.*LLM PROVIDER \(/,"",name); sub(/\).*/,"",name);
            provider=name; key=""; url="";
        }
        provider!="" && /_API_KEY=|_TOKEN=/ {
            line=$0; gsub(/^# ?/,"",line);
            if (key=="" && line ~ /=/) { split(line,a,"="); key=a[1]; }
        }
        provider!="" && /https?:\/\// && url=="" {
            u=$0; match(u,/https?:\/\/[^ ]+/); url=substr(u,RSTART,RLENGTH);
        }
        provider!="" && /^# ===/ && key!="" {
            print provider "\t" key "\t" url; provider="";
        }
    ' "$SCRIPT_DIR/.env.example")"

    while IFS=$'\t' read -r name key url; do
        [ -z "$name" ] && continue
        PROV_NAME+=("$name"); PROV_KEY+=("$key"); PROV_URL+=("$url")
    done <<< "$parsed"
}

# Suggested default model per provider key (used only for one-shot providers).
suggest_model() {
    case "$1" in
        OPENROUTER_API_KEY) echo "anthropic/claude-opus-4.6" ;;
        GOOGLE_API_KEY)     echo "gemini-3-pro-preview" ;;
        *)                  echo "" ;;
    esac
}

# ----------------------------------------------------------------------------
# Run a hermes subcommand in whichever mode is active.
# ----------------------------------------------------------------------------
MODE=""          # "native" | "docker"
HERMES_BIN=""    # path to the venv hermes in native mode

hermes_cli() {
    if [ "$MODE" = "native" ]; then
        "$HERMES_BIN" "$@"
    else
        docker compose -f "$SCRIPT_DIR/docker-compose.yml" run --rm gateway "$@"
    fi
}

hermes_cli_tty() {
    if [ "$MODE" = "native" ]; then
        "$HERMES_BIN" "$@"
    else
        docker compose -f "$SCRIPT_DIR/docker-compose.yml" run --rm -it gateway "$@"
    fi
}

# ----------------------------------------------------------------------------
# Step 1 — deployment mode
# ----------------------------------------------------------------------------
choose_mode() {
    hdr "Deployment mode"
    cat <<EOF
  How should Hermes run on this server?

    ${BOLD}1) Native${NC}  — Python venv (uv) + a systemd user service.
                Lightest weight. The agent's terminal tool runs directly
                on this host, so it can act on the server itself.

    ${BOLD}2) Docker${NC}  — docker compose (gateway + dashboard), s6-supervised,
                restart=unless-stopped. Isolated & reproducible; the agent's
                shell commands run inside the container, not on the host.

  Rule of thumb: pick ${BOLD}Docker${NC} for an isolated, reproducible box you
  mostly leave alone; pick ${BOLD}Native${NC} when you want the agent to operate
  on this machine directly, or you'd rather manage it with systemd.
EOF
    local choice
    choice="$(ask 'Choose 1 (native) or 2 (docker)' '1')"
    case "$choice" in
        2) MODE="docker" ;;
        *) MODE="native" ;;
    esac
    ok "Mode: $MODE"
}

# ----------------------------------------------------------------------------
# Step 2 — dependencies
# ----------------------------------------------------------------------------
install_native() {
    hdr "Installing dependencies (native)"
    if [ ! -x "$SCRIPT_DIR/setup-hermes.sh" ]; then
        err "setup-hermes.sh not found or not executable — cannot install natively."
        exit 1
    fi
    log "Delegating to ./setup-hermes.sh (venv + uv sync + skills)…"
    # setup-hermes.sh ends with two interactive prompts (install ripgrep? run
    # the wizard?). We decline both — this bootstrap drives configuration
    # itself — by feeding 'n' answers on stdin.
    printf 'n\nn\n' | "$SCRIPT_DIR/setup-hermes.sh"

    HERMES_BIN="$SCRIPT_DIR/venv/bin/hermes"
    if [ ! -x "$HERMES_BIN" ]; then
        err "Expected hermes binary at $HERMES_BIN but it is missing."
        exit 1
    fi
    ok "Dependencies installed — hermes at $HERMES_BIN"
}

install_docker() {
    hdr "Building the Docker image"
    if ! command -v docker >/dev/null 2>&1; then
        err "docker not found. Install Docker Engine first: https://docs.docker.com/engine/install/"
        exit 1
    fi
    if ! docker compose version >/dev/null 2>&1; then
        err "The Docker Compose plugin is required (docker compose ...)."
        err "Install it: https://docs.docker.com/compose/install/"
        exit 1
    fi
    mkdir -p "$HERMES_HOME"
    log "Building image (first build can take several minutes)…"
    docker compose -f "$SCRIPT_DIR/docker-compose.yml" build
    ok "Image built"
}

# ----------------------------------------------------------------------------
# Step 3 + 4 — AI provider choice and keys
# ----------------------------------------------------------------------------
configure_ai() {
    hdr "AI provider"
    load_providers
    local n=${#PROV_NAME[@]}
    if [ "$n" -eq 0 ]; then
        warn "Could not parse any providers from .env.example."
        warn "You can configure one later with:  hermes model"
        return
    fi

    echo "  Choose how Hermes reaches its main chat model:"
    echo
    local i
    for i in $(seq 0 $((n - 1))); do
        local tag=""
        [ "${PROV_KEY[$i]}" = "OPENROUTER_API_KEY" ] && tag="  ${GREEN}(recommended — one key, every model)${NC}"
        printf '   %2d) %-34s %b%s%b%b\n' "$((i + 1))" "${PROV_NAME[$i]}" "$DIM" "${PROV_KEY[$i]}" "$NC" "$tag"
    done
    local portal_idx=$((n + 1)) skip_idx=$((n + 2))
    printf '   %2d) %s\n' "$portal_idx" "Nous Portal (free OAuth login — no API key)"
    printf '   %2d) %s\n' "$skip_idx"   "Skip — I'll run 'hermes model' myself later"
    echo

    local pick
    pick="$(ask "Select provider [1-$skip_idx]" '1')"

    # Non-numeric or out of range → skip safely.
    if ! [[ "$pick" =~ ^[0-9]+$ ]] || [ "$pick" -lt 1 ] || [ "$pick" -gt "$skip_idx" ]; then
        warn "No valid selection — skipping provider setup."
        return
    fi

    if [ "$pick" -eq "$skip_idx" ]; then
        warn "Skipped. Configure later with:  hermes model"
        return
    fi

    if [ "$pick" -eq "$portal_idx" ]; then
        log "Launching the Nous Portal login (browser / device-code flow)…"
        hermes_cli_tty login || warn "Portal login did not complete — you can retry with: hermes login"
        return
    fi

    local idx=$((pick - 1))
    local name="${PROV_NAME[$idx]}" key="${PROV_KEY[$idx]}" url="${PROV_URL[$idx]}"

    echo
    ok "Selected: $name"
    [ -n "$url" ] && log "Get a key at: $url"
    local val
    val="$(ask_secret "Paste your $key (leave blank to skip)")"
    if [ -z "$val" ]; then
        warn "No key entered — skipping. Configure later with: hermes model"
        return
    fi
    set_env_kv "$key" "$val"
    ok "Saved $key to $ENV_FILE"

    # OpenRouter (and the OpenAI-compatible fallback) are the one-key-does-all
    # paths — the default routing already points there, so a bare model slug
    # is enough for a true one-shot. Other providers need base_url / provider
    # wiring, which the project's own picker does correctly — hand off to it.
    if [ "$key" = "OPENROUTER_API_KEY" ]; then
        local default_model model
        default_model="$(suggest_model "$key")"
        model="$(ask 'Default model (OpenRouter slug)' "$default_model")"
        if [ -n "$model" ]; then
            if hermes_cli config set model "$model" >/dev/null 2>&1; then
                ok "Default model set to $model"
            else
                warn "Could not set the default model automatically."
                warn "Set it later with:  hermes config set model $model"
            fi
        fi
    else
        echo
        log "This provider needs model/endpoint wiring. Finishing with the"
        log "built-in picker so it is configured correctly…"
        hermes_cli_tty model || warn "Model selection skipped — rerun anytime with: hermes model"
    fi

    # Offer to stash additional provider keys as fallbacks.
    while yesno "Add another provider API key (fallback)?" "N"; do
        add_extra_provider_key
    done
}

add_extra_provider_key() {
    local n=${#PROV_NAME[@]} i pick
    for i in $(seq 0 $((n - 1))); do
        printf '   %2d) %-34s %b%s%b\n' "$((i + 1))" "${PROV_NAME[$i]}" "$DIM" "${PROV_KEY[$i]}" "$NC"
    done
    pick="$(ask "Which provider? [1-$n]" '')"
    if ! [[ "$pick" =~ ^[0-9]+$ ]] || [ "$pick" -lt 1 ] || [ "$pick" -gt "$n" ]; then
        warn "Skipped."
        return
    fi
    local idx=$((pick - 1)) val
    [ -n "${PROV_URL[$idx]}" ] && log "Get a key at: ${PROV_URL[$idx]}"
    val="$(ask_secret "Paste your ${PROV_KEY[$idx]}")"
    if [ -n "$val" ]; then
        set_env_kv "${PROV_KEY[$idx]}" "$val"
        ok "Saved ${PROV_KEY[$idx]}"
    fi
}

# ----------------------------------------------------------------------------
# Step 5 — Google Workspace OAuth (Gmail / Calendar / Drive)
# ----------------------------------------------------------------------------
configure_google() {
    hdr "Google Workspace (Gmail / Calendar / Drive) — optional"
    cat <<EOF
  This is an OAuth flow, not a single API key. You need an OAuth ${BOLD}client
  secret JSON${NC} from Google Cloud Console (APIs & Services → Credentials →
  "OAuth client ID" → Desktop app → Download JSON), with the Gmail / Calendar
  / Drive APIs enabled on the project.
EOF
    if ! yesno "Configure Google Workspace access now?" "N"; then
        log "Skipped. Run it anytime later — the flow lives in:"
        log "  skills/productivity/google-workspace/scripts/setup.py"
        return
    fi

    local secret_path
    secret_path="$(ask 'Path to your downloaded client_secret JSON (blank to skip)' '')"
    if [ -z "$secret_path" ] || [ ! -f "$secret_path" ]; then
        warn "No readable client-secret file provided — skipping Google setup."
        return
    fi

    local py setup_script docker_secret
    setup_script="skills/productivity/google-workspace/scripts/setup.py"

    if [ "$MODE" = "native" ]; then
        py="$SCRIPT_DIR/venv/bin/python"
        run_gw() { "$py" "$SCRIPT_DIR/$setup_script" "$@"; }
        local secret_arg="$secret_path"
    else
        # The container reads files under /opt/data (the ~/.hermes mount), so
        # stage the secret there and reference it by its in-container path.
        docker_secret="$HERMES_HOME/google_client_secret_incoming.json"
        cp "$secret_path" "$docker_secret"
        run_gw() {
            docker compose -f "$SCRIPT_DIR/docker-compose.yml" run --rm \
                gateway python "/opt/hermes/$setup_script" "$@"
        }
        local secret_arg="/opt/data/google_client_secret_incoming.json"
    fi

    log "Installing Google API dependencies…"
    run_gw --install-deps || warn "Dependency install reported an issue; continuing."

    log "Storing client credentials…"
    if ! run_gw --client-secret "$secret_arg"; then
        err "Could not store the client secret. Aborting Google setup."
        return
    fi

    log "Generating the authorization URL…"
    echo
    echo "  ${BOLD}Open this URL in a browser, approve access, then copy the code${NC}"
    echo "  (it appears in the address bar after the redirect / on the page):"
    echo
    run_gw --auth-url || { err "Could not generate the auth URL."; return; }
    echo
    local code
    code="$(ask 'Paste the authorization code here' '')"
    if [ -z "$code" ]; then
        warn "No code entered — Google setup left incomplete. Rerun setup.py --auth-code later."
        return
    fi
    if run_gw --auth-code "$code" && run_gw --check; then
        ok "Google Workspace authorized."
    else
        warn "Authorization did not verify. You can retry the flow later."
    fi
}

# ----------------------------------------------------------------------------
# Step 6 — a few common optional tool keys
# ----------------------------------------------------------------------------
configure_extras() {
    hdr "Extra tool keys — optional"
    if ! yesno "Configure optional tools (web search / Telegram / GitHub) now?" "N"; then
        log "Skipped. Add these later with 'hermes setup tools' or by editing $ENV_FILE."
        return
    fi

    local v
    v="$(ask_secret 'EXA_API_KEY — AI web search (blank to skip)')"
    [ -n "$v" ] && { set_env_kv EXA_API_KEY "$v"; ok "Saved EXA_API_KEY"; }

    v="$(ask_secret 'TELEGRAM_BOT_TOKEN — Telegram gateway (blank to skip)')"
    if [ -n "$v" ]; then
        set_env_kv TELEGRAM_BOT_TOKEN "$v"
        local users
        users="$(ask 'TELEGRAM_ALLOWED_USERS (comma-separated user IDs)' '')"
        [ -n "$users" ] && set_env_kv TELEGRAM_ALLOWED_USERS "$users"
        ok "Saved Telegram settings"
    fi

    v="$(ask_secret 'GITHUB_TOKEN — Skills Hub / GitHub tools (blank to skip)')"
    [ -n "$v" ] && { set_env_kv GITHUB_TOKEN "$v"; ok "Saved GITHUB_TOKEN"; }
}

# ----------------------------------------------------------------------------
# Step 7 — start the agent
# ----------------------------------------------------------------------------
start_native() {
    hdr "Start Hermes (native)"
    cat <<EOF
    1) Install a systemd ${BOLD}user${NC} service (recommended — survives logout,
       auto-restarts). Runs the messaging gateway in the background.
    2) Run the gateway in the ${BOLD}foreground${NC} now (Ctrl-C to stop).
    3) Do nothing — I'll start it myself.
EOF
    local choice
    choice="$(ask 'Choose 1, 2 or 3' '1')"
    case "$choice" in
        1)
            log "Installing the gateway service…"
            if "$HERMES_BIN" gateway install; then
                ok "Gateway service installed."
                echo "   Manage it with:  hermes gateway status | stop | start"
            else
                warn "Service install failed — you can run it in the foreground with:"
                echo "   $HERMES_BIN gateway run"
            fi
            ;;
        2)
            log "Starting the gateway in the foreground (Ctrl-C to stop)…"
            exec "$HERMES_BIN" gateway run
            ;;
        *)
            log "Left stopped. Start later with:  $HERMES_BIN gateway run"
            ;;
    esac
}

start_docker() {
    hdr "Start Hermes (Docker)"
    if yesno "Start the containers now (docker compose up -d)?" "Y"; then
        HERMES_UID="$(id -u)" HERMES_GID="$(id -g)" \
            docker compose -f "$SCRIPT_DIR/docker-compose.yml" up -d
        ok "Containers started."
        echo "   Logs:     docker compose logs -f gateway"
        echo "   Stop:     docker compose down"
        echo "   Dashboard is bound to 127.0.0.1:9119 (SSH-tunnel to reach it)."
    else
        log "Left stopped. Start later with:"
        echo "   HERMES_UID=\$(id -u) HERMES_GID=\$(id -g) docker compose up -d"
    fi
}

# ----------------------------------------------------------------------------
# Summary
# ----------------------------------------------------------------------------
final_summary() {
    hdr "Done"
    ok  "Config directory: $HERMES_HOME"
    echo "   • API keys:    $ENV_FILE"
    echo "   • Settings:    $HERMES_HOME/config.yaml"
    echo
    if [ "$MODE" = "native" ]; then
        echo "   Chat now:      $HERMES_BIN chat"
        echo "   Reconfigure:   $HERMES_BIN setup     (full interactive wizard)"
        echo "   Diagnostics:   $HERMES_BIN doctor"
    else
        echo "   Chat now:      docker compose run --rm -it gateway chat"
        echo "   Reconfigure:   docker compose run --rm -it gateway setup"
        echo "   Diagnostics:   docker compose run --rm gateway doctor"
    fi
    echo
}

# ----------------------------------------------------------------------------
main() {
    require_tty
    printf '\n%b⚕ Hermes Agent — server bootstrap%b\n' "${CYAN}${BOLD}" "$NC"

    choose_mode
    case "$MODE" in
        native) install_native ;;
        docker) install_docker ;;
    esac

    configure_ai
    configure_google
    configure_extras

    case "$MODE" in
        native) start_native ;;
        docker) start_docker ;;
    esac

    final_summary
}

main "$@"
