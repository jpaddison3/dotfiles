#!/bin/bash
set -euo pipefail

# Claude MCP Mode Switcher
# Switches between different MCP server configurations to manage context token usage

# === Configuration ===
CLAUDE_CONFIG="$HOME/.claude.json"
BACKUP_DIR="$HOME/.claude/mcp-backups"
MODES_FILE="$HOME/Documents/dotfiles/claude-mcp-modes.json"
STATE_FILE="$HOME/.claude/.mcp-mode-state"
LOCK_FILE="/tmp/claude-mcp-mode.lock"
MAX_BACKUPS=5

# === Color output ===
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() { echo -e "${BLUE}[cmode]${NC} $1"; }
log_success() { echo -e "${GREEN}[cmode]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[cmode]${NC} $1"; }
log_error() { echo -e "${RED}[cmode]${NC} $1" >&2; }

# === Locking ===
acquire_lock() {
    # macOS doesn't have flock, use mkdir-based locking
    if ! mkdir "$LOCK_FILE" 2>/dev/null; then
        # Check if lock is stale (older than 60 seconds)
        if [[ -d "$LOCK_FILE" ]]; then
            local lock_age
            lock_age=$(( $(date +%s) - $(stat -f %m "$LOCK_FILE" 2>/dev/null || echo 0) ))
            if [[ $lock_age -gt 60 ]]; then
                rmdir "$LOCK_FILE" 2>/dev/null || true
                mkdir "$LOCK_FILE" 2>/dev/null || true
            else
                log_error "Another instance is running. Aborting."
                exit 1
            fi
        fi
    fi
    # Clean up lock on exit
    trap 'rmdir "$LOCK_FILE" 2>/dev/null || true' EXIT
}

# === Validation ===
validate_json_file() {
    local file="$1"
    if ! jq empty "$file" 2>/dev/null; then
        return 1
    fi
    return 0
}

check_claude_running() {
    if pgrep -f "claude" >/dev/null 2>&1; then
        log_warn "Claude appears to be running."
        log_warn "Changes will take effect when you restart Claude Code."
        echo ""
    fi
}

# === Backup functions ===
ensure_backup_dir() {
    mkdir -p "$BACKUP_DIR"
}

create_backup() {
    local timestamp
    timestamp=$(date +%Y-%m-%dT%H-%M-%S)
    local backup_file="$BACKUP_DIR/claude.json.$timestamp.bak"
    cp "$CLAUDE_CONFIG" "$backup_file"

    # Also save as "pre-switch" for easy restore
    cp "$CLAUDE_CONFIG" "$BACKUP_DIR/claude.json.pre-mcp-switch.bak"

    # Cleanup old backups (keep MAX_BACKUPS)
    ls -t "$BACKUP_DIR"/claude.json.2*.bak 2>/dev/null | tail -n +$((MAX_BACKUPS + 1)) | xargs -r rm -f

    log_info "Backup created: $backup_file"
}

# === Config sync ===
sync_current_configs() {
    # Capture current server configs from ~/.claude.json to modes file
    # This preserves any changes made directly to ~/.claude.json
    local current_servers
    current_servers=$(jq -r '.mcpServers // {} | keys[]' "$CLAUDE_CONFIG" 2>/dev/null)

    if [[ -z "$current_servers" ]]; then
        return 0  # No servers to sync
    fi

    local modes_content
    modes_content=$(cat "$MODES_FILE")

    for server in $current_servers; do
        local server_config
        server_config=$(jq ".mcpServers.\"$server\"" "$CLAUDE_CONFIG")
        if [[ "$server_config" != "null" ]]; then
            modes_content=$(echo "$modes_content" | jq ".serverConfigs.\"$server\" = $server_config")
        fi
    done

    # Write updated modes file
    local temp_file
    temp_file=$(mktemp)
    echo "$modes_content" > "$temp_file"

    if validate_json_file "$temp_file"; then
        mv "$temp_file" "$MODES_FILE"
        log_info "Synced current server configs to modes file"
    else
        log_warn "Failed to sync configs (invalid JSON), continuing with existing configs"
        rm -f "$temp_file"
    fi
}

# === Core mode switching ===
get_current_servers() {
    jq -r '.mcpServers // {} | keys[]' "$CLAUDE_CONFIG" 2>/dev/null | sort | tr '\n' ' ' | sed 's/ $//'
}

get_current_mode() {
    if [[ -f "$STATE_FILE" ]]; then
        cat "$STATE_FILE"
    else
        # Try to detect from current servers
        local current_servers
        current_servers=$(get_current_servers)
        if [[ -z "$current_servers" ]]; then
            echo "minimal"
        elif [[ "$current_servers" == "zen" ]]; then
            echo "lite"
        elif [[ "$current_servers" == "betterstack sentry zen" ]]; then
            echo "full"
        else
            echo "custom"
        fi
    fi
}

get_available_modes() {
    jq -r '.modes | keys[]' "$MODES_FILE" 2>/dev/null | tr '\n' ' ' | sed 's/ $//'
}

switch_mode() {
    local target_mode="$1"

    # Check mode exists
    if ! jq -e ".modes.\"$target_mode\"" "$MODES_FILE" >/dev/null 2>&1; then
        log_error "Mode '$target_mode' not found."
        echo ""
        show_modes
        exit 1
    fi

    # Get servers for this mode
    local servers_list
    servers_list=$(jq -r ".modes.\"$target_mode\".servers[]?" "$MODES_FILE" 2>/dev/null)

    # Build new mcpServers object
    local new_mcp_servers="{}"
    for server in $servers_list; do
        local server_config
        server_config=$(jq ".serverConfigs.\"$server\"" "$MODES_FILE")
        if [[ "$server_config" != "null" ]]; then
            new_mcp_servers=$(echo "$new_mcp_servers" | jq ". + {\"$server\": $server_config}")
        else
            log_warn "Server '$server' not found in serverConfigs, skipping"
        fi
    done

    # Read current config
    local current_config
    current_config=$(cat "$CLAUDE_CONFIG")

    # Merge new mcpServers
    local new_config
    new_config=$(echo "$current_config" | jq ".mcpServers = $new_mcp_servers")

    # Write to temp file
    local temp_file
    temp_file=$(mktemp)
    echo "$new_config" > "$temp_file"

    # Validate before writing
    if ! validate_json_file "$temp_file"; then
        log_error "Generated invalid JSON! Aborting."
        rm -f "$temp_file"
        exit 1
    fi

    # Atomic move
    mv "$temp_file" "$CLAUDE_CONFIG"

    # Update state
    echo "$target_mode" > "$STATE_FILE"

    # Report success
    log_success "Switched to '$target_mode' mode"
    local active_servers
    active_servers=$(get_current_servers)
    if [[ -n "$active_servers" ]]; then
        log_info "Active servers: $active_servers"
    else
        log_info "Active servers: (none)"
    fi
    echo ""
    log_warn "Restart Claude Code for changes to take effect"
}

show_status() {
    local current_mode
    current_mode=$(get_current_mode)
    local current_servers
    current_servers=$(get_current_servers)

    echo ""
    echo -e "Claude MCP Mode: ${GREEN}$current_mode${NC}"
    echo "Active servers: ${current_servers:-"(none)"}"
    echo ""
    show_modes "$current_mode"
}

show_modes() {
    local current="${1:-}"
    echo "Available modes:"
    while IFS= read -r line; do
        local mode_name
        mode_name=$(echo "$line" | cut -d'|' -f1)
        local description
        description=$(echo "$line" | cut -d'|' -f2)
        if [[ "$mode_name" == "$current" ]]; then
            echo -e "  ${GREEN}$mode_name${NC}\t- $description ${GREEN}[CURRENT]${NC}"
        else
            echo -e "  $mode_name\t- $description"
        fi
    done < <(jq -r '.modes | to_entries[] | "\(.key)|\(.value.description)"' "$MODES_FILE")
}

# === Restore functionality ===
restore_backup() {
    echo "Available backups:"
    local backups
    mapfile -t backups < <(ls -t "$BACKUP_DIR"/claude.json.2*.bak 2>/dev/null)

    if [[ ${#backups[@]} -eq 0 ]]; then
        log_error "No backups found"
        exit 1
    fi

    for i in "${!backups[@]}"; do
        local backup="${backups[$i]}"
        local date
        date=$(basename "$backup" | sed 's/claude.json.\(.*\).bak/\1/')
        echo "  $((i+1))) $date"
    done

    echo ""
    read -rp "Select backup to restore (1-${#backups[@]}), or 'q' to cancel: " selection

    if [[ "$selection" == "q" ]]; then
        echo "Cancelled."
        exit 0
    fi

    if [[ "$selection" =~ ^[0-9]+$ ]] && [[ "$selection" -ge 1 ]] && [[ "$selection" -le ${#backups[@]} ]]; then
        local selected="${backups[$((selection-1))]}"
        create_backup  # Backup current before restore
        cp "$selected" "$CLAUDE_CONFIG"
        log_success "Restored from $selected"

        # Clear state file since we don't know what mode this is
        rm -f "$STATE_FILE"
    else
        log_error "Invalid selection"
        exit 1
    fi
}

show_help() {
    echo "Usage: cmode [mode|--status|--list|--restore|--backup]"
    echo ""
    echo "Switch between Claude Code MCP server configurations."
    echo ""
    echo "Modes:"
    get_available_modes | tr ' ' '\n' | sed 's/^/  /'
    echo ""
    echo "Options:"
    echo "  (no args)    Show current mode and available modes"
    echo "  --status     Same as no args"
    echo "  --list       List available modes with descriptions"
    echo "  --restore    Restore from backup"
    echo "  --backup     Create manual backup"
    echo "  --help, -h   Show this help"
    echo ""
    echo "After switching modes, restart Claude Code for changes to take effect."
}

# === Main ===
main() {
    # Validate dependencies
    if ! command -v jq &>/dev/null; then
        log_error "jq is required but not installed. Install with: brew install jq"
        exit 1
    fi

    # Validate modes file exists
    if [[ ! -f "$MODES_FILE" ]]; then
        log_error "Modes file not found: $MODES_FILE"
        exit 1
    fi

    # Validate claude config exists
    if [[ ! -f "$CLAUDE_CONFIG" ]]; then
        log_error "Claude config not found: $CLAUDE_CONFIG"
        exit 1
    fi

    case "${1:-}" in
        ""|--status)
            show_status
            ;;
        --list)
            show_modes
            ;;
        --restore)
            acquire_lock
            ensure_backup_dir
            restore_backup
            ;;
        --backup)
            acquire_lock
            ensure_backup_dir
            create_backup
            log_success "Manual backup created"
            ;;
        --help|-h)
            show_help
            ;;
        -*)
            log_error "Unknown option: $1"
            echo ""
            show_help
            exit 1
            ;;
        *)
            # Validate config before switching
            if ! validate_json_file "$CLAUDE_CONFIG"; then
                log_error "~/.claude.json contains invalid JSON!"
                log_error "Run 'cmode --restore' to restore from backup"
                exit 1
            fi

            acquire_lock
            ensure_backup_dir
            check_claude_running
            create_backup
            sync_current_configs
            switch_mode "$1"
            ;;
    esac
}

main "$@"
