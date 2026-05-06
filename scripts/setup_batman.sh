#!/usr/bin/env bash
# setup_batman.sh — Configuración de BATMAN-adv para batman-mesh-chat
#
# Uso:
#   sudo bash setup_batman.sh <interfaz_wifi>
#   Ejemplo: sudo bash setup_batman.sh wlan0
#
# Qué hace:
#   1. Instala batctl (herramienta de control de batman-adv)
#   2. Carga el módulo del kernel batman-adv
#   3. Configura la interfaz WiFi en modo ad-hoc (IBSS)
#   4. Une la interfaz a batman-adv → crea bat0
#   5. Asigna una IP a bat0 con avahi/zeroconf o DHCP según disponibilidad
#
# Para persistir el setup al reiniciar, añade este script a /etc/rc.local
# o crea un servicio systemd con el ejemplo al final de este archivo.

set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()  { echo -e "${GREEN}[✓]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
error() { echo -e "${RED}[✗]${NC} $*"; exit 1; }

# ── Parámetros ───────────────────────────────────────────────────────────────
IFACE="${1:-wlan0}"
MESH_SSID="batman-mesh"
MESH_FREQ="2412"          # Canal 1 (2.4 GHz). Todos los nodos DEBEN usar el mismo.
BAT_IFACE="bat0"
IP_PREFIX="10.20.30"      # Los nodos tomarán IPs como 10.20.30.X
MESH_IP="${IP_PREFIX}.$((RANDOM % 200 + 10))"  # IP aleatoria para evitar colisiones

[[ $EUID -ne 0 ]] && error "Ejecuta como root: sudo bash $0 $IFACE"

echo ""
echo "🦇  batman-mesh-chat — Setup de red mesh"
echo "  Interfaz : $IFACE"
echo "  SSID     : $MESH_SSID"
echo "  IP local : $MESH_IP/24"
echo ""

# ── Dependencias ─────────────────────────────────────────────────────────────
PKGS=()
command -v batctl &>/dev/null || PKGS+=(batctl)
command -v iw     &>/dev/null || PKGS+=(iw)
command -v iwconfig &>/dev/null || PKGS+=(wireless-tools)

if [[ ${#PKGS[@]} -gt 0 ]]; then
    info "Instalando: ${PKGS[*]}..."
    apt-get update -qq
    apt-get install -y "${PKGS[@]}" --no-install-recommends
fi
info "batctl $(batctl -v 2>&1 | head -1)"

# ── Módulo del kernel ─────────────────────────────────────────────────────────
if ! lsmod | grep -q batman_adv; then
    modprobe batman-adv
fi
info "Módulo batman-adv cargado"

# ── Configurar interfaz en modo ad-hoc ───────────────────────────────────────
ip link set "$IFACE" down
iw dev "$IFACE" set type ibss
ip link set "$IFACE" up
iw dev "$IFACE" ibss join "$MESH_SSID" "$MESH_FREQ"
info "Interfaz $IFACE en modo ad-hoc (IBSS) → SSID: $MESH_SSID"

# ── Añadir interfaz a batman-adv ─────────────────────────────────────────────
batctl if add "$IFACE"
ip link set "$BAT_IFACE" up
info "batman-adv activo en $BAT_IFACE"

# ── Asignar IP ───────────────────────────────────────────────────────────────
ip addr flush dev "$BAT_IFACE" 2>/dev/null || true
ip addr add "${MESH_IP}/24" dev "$BAT_IFACE"
info "IP asignada: $MESH_IP/24 en $BAT_IFACE"

# ── Verificación ─────────────────────────────────────────────────────────────
echo ""
info "Estado de la red mesh:"
batctl n 2>/dev/null | head -20 || true
echo ""
info "Interfaces batman-adv:"
batctl if 2>/dev/null || true

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
info "Setup completo."
echo ""
echo "  Tu IP en la malla : $MESH_IP"
echo "  Interfaz mesh     : $BAT_IFACE"
echo "  Peers cercanos    : batctl n"
echo "  Ver estadísticas  : batctl s"
echo ""
warn "Para persistir al reiniciar, añade los comandos a /etc/rc.local"
warn "o crea un servicio systemd (ver comentarios al final de este script)"
echo ""

# ──────────────────────────────────────────────────────────────────────────────
# EJEMPLO DE SERVICIO SYSTEMD (descomenta y copia a /etc/systemd/system/batman-mesh.service)
# ──────────────────────────────────────────────────────────────────────────────
#
# [Unit]
# Description=BATMAN-adv mesh network
# After=network.target
#
# [Service]
# Type=oneshot
# ExecStart=/bin/bash /ruta/a/scripts/setup_batman.sh wlan0
# RemainAfterExit=yes
#
# [Install]
# WantedBy=multi-user.target
#
# Activar con:
#   sudo systemctl daemon-reload
#   sudo systemctl enable batman-mesh
#   sudo systemctl start batman-mesh
