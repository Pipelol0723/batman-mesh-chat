"""
config.py — Configuración de batman-mesh-chat
Guarda y carga preferencias del usuario en ~/.batman-chat/config.json
"""

import json
import os
from pathlib import Path

CONFIG_DIR = Path.home() / ".batman-chat"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_CONFIG = {
    "username": "",
    "network_passphrase": "batman-mesh",
    "msg_port": 9999,
    "transfer_port": 9998,
    "save_dir": str(Path.home() / "batman-chat-files"),
    "max_history": 200,
}


def load_config() -> dict:
    """Carga la config, fusionando con defaults si faltan campos."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            return {**DEFAULT_CONFIG, **saved}
        except (json.JSONDecodeError, OSError):
            pass
    return DEFAULT_CONFIG.copy()


def save_config(config: dict) -> None:
    """Guarda la config en disco."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def setup_first_run() -> dict:
    """
    Primer arranque: pide username por consola y guarda config.
    Retorna el dict de config listo para usar.
    """
    config = load_config()

    if not config["username"]:
        print("\n🦇  batman-mesh-chat — Primera configuración\n")
        while True:
            username = input("  Tu nombre de usuario (sin espacios): ").strip()
            if username and " " not in username and len(username) <= 20:
                break
            print("  ⚠  Nombre inválido: sin espacios, máx 20 caracteres.")

        passphrase = input(
            f"  Contraseña de red [{config['network_passphrase']}]: "
        ).strip()
        if passphrase:
            config["network_passphrase"] = passphrase

        config["username"] = username
        save_config(config)
        print(f"\n  ✅  Config guardada en {CONFIG_FILE}\n")

    return config
