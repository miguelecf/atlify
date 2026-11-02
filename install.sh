#!/bin/sh
# Installs Atlify as an agent skill: link (or copy) into <skills>/atlify.
set -eu

SKILL=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
NOMBRE=atlify
MARCADOR=.atlify-install
MODO=enlazar
UNINSTALL=0
FORCE=0
ONLY=""

uso() {
  cat <<'EOF'
Usage: ./install.sh [--copy] [--only agents,claude,...] [--force] [--uninstall]

Without arguments it links this directory as `atlify` into ~/.agents/skills
(created if missing) and into every skill directory that already exists:
~/.claude/skills, ~/.codex/skills, ~/.pi/agent/skills,
~/.config/opencode/skills and ~/.gemini/skills.

  --copy       copy the skill instead of linking it
  --only ...   limit targets: agents, claude, codex, pi, opencode, gemini
  --force      replace a target that is not Atlify's
  --uninstall  remove only what this script installed
  --help       show this help
EOF
}

destino_de() {
  case "$1" in
    agents) echo "$HOME/.agents/skills" ;;
    claude) echo "$HOME/.claude/skills" ;;
    codex) echo "$HOME/.codex/skills" ;;
    pi) echo "$HOME/.pi/agent/skills" ;;
    opencode) echo "$HOME/.config/opencode/skills" ;;
    gemini) echo "$HOME/.gemini/skills" ;;
    *) return 1 ;;
  esac
}

apunta_al_skill() {
  [ -L "$1" ] || return 1
  destino=$(readlink "$1") || return 1
  case "$destino" in
    /*) ;;
    *) destino=$(dirname "$1")/$destino ;;
  esac
  real=$(CDPATH= cd -- "$destino" 2>/dev/null && pwd -P) || return 1
  [ "$real" = "$SKILL" ]
}

es_copia_nuestra() {
  [ -d "$1" ] && [ ! -L "$1" ] && [ -f "$1/$MARCADOR" ] && grep -qx "atlify-install" "$1/$MARCADOR" 2>/dev/null
}

escribir_marcador() {
  printf 'atlify-install\n%s\n' "$SKILL" > "$1/$MARCADOR"
}

instalar_enlace() {
  dir=$1
  dest=$dir/$NOMBRE
  if apunta_al_skill "$dest"; then
    echo "already present $dest"
    return
  fi
  if [ -e "$dest" ] || [ -L "$dest" ]; then
    if es_copia_nuestra "$dest" || [ "$FORCE" -eq 1 ]; then
      rm -rf "$dest"
    else
      echo "skipped: $dest exists and is not Atlify (use --force)"
      return
    fi
  fi
  ln -s "$SKILL" "$dest"
  echo "linked $dest -> $SKILL"
}

copiar_skill() {
  dir=$1
  dest=$dir/$NOMBRE
  if es_copia_nuestra "$dest"; then
    rm -rf "$dest"  # an older copy of ours: refresh it instead of staying stale
  fi
  if [ -e "$dest" ] || [ -L "$dest" ]; then
    if apunta_al_skill "$dest" || [ "$FORCE" -eq 1 ]; then
      rm -rf "$dest"
    else
      echo "skipped: $dest exists and is not Atlify (use --force)"
      return
    fi
  fi
  mkdir -p "$dest"
  (cd "$SKILL" && tar -cf - --exclude .git --exclude .atlify --exclude __pycache__ \
    --exclude docs --exclude 'evals/e2e/node_modules' --exclude 'evals/e2e/capturas' .) | (cd "$dest" && tar -xf -)
  escribir_marcador "$dest"
  echo "copied $dest"
}

desinstalar() {
  dir=$1
  dest=$dir/$NOMBRE
  if apunta_al_skill "$dest" || es_copia_nuestra "$dest"; then
    rm -rf "$dest"
    echo "removed $dest"
  elif [ -e "$dest" ] || [ -L "$dest" ]; then
    echo "skipped: $dest is not Atlify"
  else
    echo "not installed: $dest"
  fi
}

while [ $# -gt 0 ]; do
  case "$1" in
    --copy) MODO=copiar ;;
    --uninstall) UNINSTALL=1 ;;
    --force) FORCE=1 ;;
    --only) shift; [ $# -gt 0 ] || { echo "Missing value for --only" >&2; exit 2; }; ONLY=$1 ;;
    --only=*) ONLY=${1#--only=} ;;
    -h|--help) uso; exit 0 ;;
    *) echo "Unknown option: $1 (use --help)" >&2; exit 2 ;;
  esac
  shift
done

: "${HOME:?Missing HOME}"

DESTINOS="agents claude codex pi opencode gemini"
if [ -n "$ONLY" ]; then
  DESTINOS=$(printf '%s' "$ONLY" | tr ',' ' ')
  for n in $DESTINOS; do
    destino_de "$n" >/dev/null || { echo "Unknown target: $n (use agents, claude, codex, pi, opencode, gemini)" >&2; exit 2; }
  done
fi

for n in $DESTINOS; do
  dir=$(destino_de "$n")
  if [ "$n" = agents ] && [ "$UNINSTALL" -eq 0 ]; then
    mkdir -p "$dir"
  fi
  if [ ! -d "$dir" ]; then
    if [ "$UNINSTALL" -eq 1 ]; then
      echo "not installed: $dir does not exist"
    else
      echo "skipped: $dir (does not exist)"
    fi
    continue
  fi
  if [ "$UNINSTALL" -eq 1 ]; then
    desinstalar "$dir"
  elif [ "$MODO" = copiar ]; then
    copiar_skill "$dir"
  else
    instalar_enlace "$dir"
  fi
done
