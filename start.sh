#!/usr/bin/env bash
# start.sh — Arranca batman-mesh-chat completo en un solo paso
#
# Uso:
#   bash start.sh              # detecta la interfaz WiFi automáticamente
#   bash start.sh wlan0        # especifica la interfaz manualmente

set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()  { echo -e "${GREEN}[✓]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
error() { echo -e "${RED}[✗]${NC} $*"; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo ""
echo "🦇  batman-mesh-chat — Inicio"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ── Detectar interfaz WiFi ────────────────────────────────────────────────────
if [[ -n "${1:-}" ]]; then
    IFACE="$1"
else
    IFACE=$(iw dev 2>/dev/null | awk '/Interface/{print $2}' | head -1)
    [[ -z "$IFACE" ]] && error "No se encontró interfaz WiFi. Especifícala: bash start.sh wlan0"
fi
info "Interfaz WiFi: $IFACE"

# ── Configurar red mesh si bat0 no está activa ────────────────────────────────
if ip link show bat0 &>/dev/null; then
    info "bat0 ya está activa"
else
    warn "bat0 no encontrada — configurando red mesh..."
    [[ $EUID -ne 0 ]] && error "Necesitas ejecutar con sudo para configurar la red: sudo bash start.sh"
    bash "$SCRIPT_DIR/scripts/setup_batman.sh" "$IFACE"
fi

# ── Corregir broadcast si es 0.0.0.0 ─────────────────────────────────────────
BAT_IP=$(ip -4 addr show bat0 2>/dev/null | awk '/inet /{print $2}' | cut -d/ -f1)
BAT_BRD=$(ip -4 addr show bat0 2>/dev/null | awk '/inet /{print $4}')

if [[ -z "$BAT_IP" ]]; then
    error "bat0 no tiene IP asignada. Ejecuta: sudo bash scripts/setup_batman.sh $IFACE"
fi

if [[ "$BAT_BRD" == "0.0.0.0" || -z "$BAT_BRD" ]]; then
    warn "Corrigiendo broadcast de bat0..."
    PREFIX=$(echo "$BAT_IP" | cut -d. -f1-3)
    if [[ $EUID -ne 0 ]]; then
        sudo ip addr flush dev bat0
        sudo ip addr add "${BAT_IP}/24" broadcast "${PREFIX}.255" dev bat0
    else
        ip addr flush dev bat0
        ip addr add "${BAT_IP}/24" broadcast "${PREFIX}.255" dev bat0
    fi
    info "Broadcast corregido: ${PREFIX}.255"
fi

info "IP en la malla: $BAT_IP"

# ── Verificar dependencias Python ─────────────────────────────────────────────
if ! python3 -c "import cryptography, textual" 2>/dev/null; then
    warn "Instalando dependencias Python..."
    pip install -r "$SCRIPT_DIR/requirements.txt" --quiet
fi

# ── Arrancar el chat ──────────────────────────────────────────────────────────
echo ""
info "Arrancando batman-mesh-chat..."
echo ""
cd "$SCRIPT_DIR"
python3 batman_chat.py
