# Source this file from ~/.zshrc or ~/.bashrc, then: ask <intent or pasted error trace>
# Override the model with ASKK_MODEL=<provider/model>.

_askk_copy() {
  if command -v pbcopy >/dev/null 2>&1; then
    printf '%s' "$1" | pbcopy
  elif command -v wl-copy >/dev/null 2>&1; then
    printf '%s' "$1" | wl-copy
  elif command -v xclip >/dev/null 2>&1; then
    printf '%s' "$1" | xclip -selection clipboard
  else
    return 1
  fi
}

ask() {
  if [ $# -eq 0 ]; then
    echo "Usage: ask <intent or pasted error trace>" >&2
    return 1
  fi

  local model="${ASKK_MODEL:-claude-agent/system.ai.claude-haiku-5-5}"
  local raw cmd
  raw=$(opencode run --agent bash --model "$model" "$*" 2>/dev/null)

  # Models sometimes add prose around a fenced block: prefer the first fenced
  # block, otherwise fall back to the first non-empty line.
  cmd=$(printf '%s\n' "$raw" | awk '
    /^[[:space:]]*```/ { if (fenced) exit; fenced = 1; next }
    fenced { body = body $0 "\n"; next }
    !first && NF { first = $0 }
    END { if (fenced) printf "%s", body; else print first }
  ' | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')

  if [ -z "$cmd" ]; then
    echo "No command generated." >&2
    return 1
  fi

  _askk_copy "$cmd" && printf '\033[2m(copied to clipboard)\033[0m\n' >&2

  if [ -n "$ZSH_VERSION" ]; then
    # Push onto the zle buffer: it appears at the next prompt, editable, Enter runs it.
    print -z -- "$cmd"
  elif [ -n "$BASH_VERSION" ] && [ "${BASH_VERSINFO[0]}" -ge 4 ]; then
    # Pre-filled, editable line: Enter runs it, Ctrl-C cancels.
    local line
    if read -r -e -i "$cmd" -p $'\033[1;36m❯\033[0m ' line && [ -n "$line" ]; then
      history -s -- "$line"
      eval "$line"
    fi
  elif [ -n "$BASH_VERSION" ]; then
    # bash 3.x (macOS /bin/bash) has no `read -i`.
    local resp
    printf '\n\033[1;36m%s\033[0m\n\n' "$cmd"
    read -r -p "Run it? [Y/n] " resp
    case "$resp" in
      [nN]*) ;;
      *) history -s -- "$cmd"; eval "$cmd" ;;
    esac
  else
    printf '\n\033[1;36m%s\033[0m\n\n' "$cmd"
  fi
}
