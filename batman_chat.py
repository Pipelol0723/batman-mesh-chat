#!/usr/bin/env python3
"""
batman_chat.py — Punto de entrada de batman-mesh-chat

Uso:
    python batman_chat.py              # lanza la TUI (configura usuario en 1er arranque)
    python batman_chat.py --reset      # borra config y vuelve a pedir usuario
    python batman_chat.py --info       # muestra config actual y sale

Requisitos:
    pip install cryptography textual

Red:
    La app funciona en cualquier red IP local (WiFi, Ethernet, etc.).
    Con BATMAN-adv (bat0), el broadcast se propaga por toda la malla mesh.

Puertos:
    UDP 9999  — mensajes y descubrimiento de peers
    TCP 9998  — transferencia de archivos
"""

import argparse
import json
import sys
from pathlib import Path

# Asegurar que el paquete chat/ sea importable desde el directorio del script
sys.path.insert(0, str(Path(__file__).parent))

from chat.config import CONFIG_FILE, load_config, save_config, setup_first_run


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="🦇 batman-mesh-chat — Chat descentralizado para redes mesh"
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Borrar configuración y volver a configurar desde cero",
    )
    parser.add_argument(
        "--info",
        action="store_true",
        help="Mostrar configuración actual y salir",
    )
    parser.add_argument(
        "--user",
        metavar="NOMBRE",
        help="Establecer nombre de usuario y salir",
    )
    parser.add_argument(
        "--passphrase",
        metavar="CLAVE",
        help="Establecer contraseña de red y salir",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # ── --reset ───────────────────────────────────────────────────────────
    if args.reset:
        if CONFIG_FILE.exists():
            CONFIG_FILE.unlink()
            print(f"✅ Config borrada: {CONFIG_FILE}")
        else:
            print("ℹ  No había config que borrar.")

    # ── --user / --passphrase ─────────────────────────────────────────────
    if args.user or args.passphrase:
        config = load_config()
        if args.user:
            config["username"] = args.user
        if args.passphrase:
            config["network_passphrase"] = args.passphrase
        save_config(config)
        print(f"✅ Config actualizada en {CONFIG_FILE}")
        if args.info:
            _print_info(config)
        return

    # ── --info ────────────────────────────────────────────────────────────
    if args.info:
        config = load_config()
        _print_info(config)
        return

    # ── Arranque normal ───────────────────────────────────────────────────
    config = setup_first_run()

    # Verificación de dependencias
    try:
        from cryptography.fernet import Fernet  # noqa: F401
    except ImportError:
        print("❌ Falta la dependencia: pip install cryptography")
        sys.exit(1)

    try:
        from textual.app import App  # noqa: F401
    except ImportError:
        print("❌ Falta la dependencia: pip install textual")
        sys.exit(1)

    # Lanzar TUI
    from chat.tui import BatmanChatApp

    app = BatmanChatApp(config)
    app.run()


def _print_info(config: dict) -> None:
    print("\n🦇 batman-mesh-chat — Configuración actual\n")
    print(f"  Usuario      : {config.get('username', '(sin configurar)')}")
    print(f"  Passphrase   : {config.get('network_passphrase')}")
    print(f"  Puerto UDP   : {config.get('msg_port')}")
    print(f"  Puerto TCP   : {config.get('transfer_port')}")
    print(f"  Directorio   : {config.get('save_dir')}")
    print(f"  Config en    : {CONFIG_FILE}\n")


if __name__ == "__main__":
    main()
