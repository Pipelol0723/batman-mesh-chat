#!/usr/bin/env bash
# install.sh — Instalador de batman-mesh-chat
# Uso: bash install.sh
# Requiere: Python 3.10+, pip

set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()    { echo -e "${GREEN}[✓]${NC} $*"; }
warn()    { echo -e "${YELLOW}[!]${NC} $*"; }
error()   { echo -e "${RED}[✗]${NC} $*"; exit 1; }

echo ""
echo "🦇  batman-mesh-chat — Instalador"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ── Python 3.10+ ────────────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
    error "Python 3 no encontrado. Instala con: sudo apt install python3"
fi

PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$(python3 -c "import sys; print(sys.version_info.major)")
PY_MINOR=$(python3 -c "import sys; print(sys.version_info.minor)")

if [[ $PY_MAJOR -lt 3 || ($PY_MAJOR -eq 3 && $PY_MINOR -lt 10) ]]; then
    error "Se requiere Python 3.10+. Versión actual: $PY_VER"
fi
info "Python $PY_VER detectado"

# ── pip ─────────────────────────────────────────────────────────────────────
if ! python3 -m pip --version &>/dev/null; then
    warn "pip no encontrado. Instalando..."
    sudo apt-get install -y python3-pip
fi
info "pip disponible"

# ── Dependencias ─────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
info "Instalando dependencias Python..."
python3 -m pip install --upgrade pip --quiet
python3 -m pip install -r "$SCRIPT_DIR/requirements.txt" --quiet
info "Dependencias instaladas"

# ── Script ejecutable ────────────────────────────────────────────────────────
chmod +x "$SCRIPT_DIR/batman_chat.py"

# ── Symlink opcional ─────────────────────────────────────────────────────────
INSTALL_LINK="/usr/local/bin/batman-chat"
if [[ -w /usr/local/bin ]]; then
    ln -sf "$SCRIPT_DIR/batman_chat.py" "$INSTALL_LINK"
    info "Acceso global: batman-chat"
else
    warn "Sin permisos para instalar en /usr/local/bin."
    warn "Puedes ejecutar con: python3 $SCRIPT_DIR/batman_chat.py"
    warn "O crear el enlace manualmente: sudo ln -sf $SCRIPT_DIR/batman_chat.py $INSTALL_LINK"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
info "Instalación completa."
echo ""
echo "  Primer uso    : python3 $SCRIPT_DIR/batman_chat.py"
echo "  Config rápida : python3 batman_chat.py --user TuNombre"
echo "  Ver config    : python3 batman_chat.py --info"
echo "  Setup batman  : bash $SCRIPT_DIR/scripts/setup_batman.sh"
echo ""
