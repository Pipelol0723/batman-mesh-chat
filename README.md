# 🦇 batman-mesh-chat

Chat descentralizado para redes mesh Linux usando [BATMAN-adv](https://www.open-mesh.org/projects/batman-adv/wiki).

- **Sin servidor central** — los mensajes se transmiten por broadcast UDP en la malla
- **Mensajes de texto** con historial SQLite local
- **Envío de archivos y fotos** cifrados por TCP
- **Cifrado Fernet** (AES-128-CBC + HMAC-SHA256) con clave derivada de passphrase
- **TUI con Textual** — interfaz de terminal moderna y responsiva
- **Cualquiera que descargue la app y esté en la red puede unirse**

---

## Captura de pantalla

```
┌─────────────────────────────────────────────────── 🦇 batman-mesh-chat — pipe ─ 14:32 ─┐
│                                                                                          │
│  ──────── historial ────────                                                             │
│  14:28 pipe: hola a todos!                                                               │
│  14:29 ana: hola pipe!                                                                   │
│  14:30 ⚡ carlos se unió a la red                                                        │
│  14:31 carlos envió 📎 documento.pdf (2.3 MB)                                           │
│  ──────── chat en vivo ─────                                                             │
│  14:32 pipe: buenas noches                                                               │
│                                                                                          │
│ 🔗 2 peer(s): ana, carlos | Red: batman-mesh                                            │
│ > _                                                                                      │
└──────────────────────────────────────────────────────────────────────────────────────────┘
  [F2 Enviar Archivo]  [F5 Ver Peers]  [Ctrl+Q Salir]
```

---

## Instalación rápida

```bash
git clone https://github.com/pipelol0723/batman-mesh-chat
cd batman-mesh-chat
bash install.sh
```

### Requisitos

- Linux (Ubuntu 20.04+ / Debian 11+ / Arch / cualquier distro con Python 3.10)
- Python 3.10 o superior
- `pip install cryptography textual`
- BATMAN-adv (opcional para WiFi mesh; funciona también en cualquier LAN local)

---

## Uso

### Primer arranque

```bash
python3 batman_chat.py
# → Pide nombre de usuario y contraseña de red
# → La config se guarda en ~/.batman-chat/config.json
```

### Opciones de línea de comandos

```bash
python3 batman_chat.py --user pipe            # Establece nombre de usuario
python3 batman_chat.py --passphrase mi-red    # Cambia la contraseña de red
python3 batman_chat.py --info                 # Muestra la config actual
python3 batman_chat.py --reset                # Borra config y reconfigura
```

### Atajos de teclado en la TUI

| Tecla   | Acción                                       |
|---------|----------------------------------------------|
| `Enter` | Enviar mensaje                               |
| `F2`    | Modo envío de archivo (pide ruta)            |
| `F5`    | Mostrar peers conectados en el log           |
| `Ctrl+L`| Limpiar pantalla (historial en DB intacto)   |
| `Ctrl+Q`| Salir limpiamente                            |

---

## Setup de red mesh con BATMAN-adv

Para usar el chat en una red mesh WiFi real (sin router):

```bash
# Instalar batman-adv y configurar interfaz mesh
sudo bash scripts/setup_batman.sh wlan0
```

El script:
1. Instala `batctl`
2. Carga el módulo `batman-adv` del kernel
3. Pone `wlan0` en modo ad-hoc con SSID `batman-mesh`
4. Crea la interfaz `bat0` con IP `10.20.30.X/24`

> **Nota:** Todos los dispositivos deben usar la misma interfaz WiFi,
> el mismo canal y el mismo SSID de mesh para verse entre sí.

### Verificar peers de la malla

```bash
batctl n          # Neighbors — peers batman directamente visibles
batctl traceroute <IP>   # Ruta hasta un peer
batctl s          # Estadísticas
```

---

## Cifrado

| Componente              | Algoritmo / Parámetros                        |
|-------------------------|-----------------------------------------------|
| Derivación de clave     | PBKDF2-HMAC-SHA256, 100 000 iteraciones       |
| Cifrado de mensajes     | Fernet (AES-128-CBC + HMAC-SHA256)            |
| Cifrado de archivos     | Fernet por chunks de 64 KB                   |
| Salt                    | Fijo por red (`batman-mesh-salt-v1`)          |
| Transporte              | UDP broadcast (mensajes) + TCP (archivos)     |

**¿Qué protege?** Cualquier observador pasivo en la red (Wireshark, etc.)
solo verá bytes cifrados. Sin la passphrase correcta, no puede leer nada.

**¿Qué NO protege?** No hay autenticación de identidad (un peer puede usar
cualquier nombre). Para redes de alta seguridad, considera añadir
certificados por usuario.

---

## Estructura del proyecto

```
batman-chat/
├── batman_chat.py       # Punto de entrada + CLI
├── chat/
│   ├── config.py        # Configuración ~/.batman-chat/config.json
│   ├── crypto.py        # Cifrado Fernet (PBKDF2 + AES)
│   ├── db.py            # Historial SQLite (~/.batman-chat/history.db)
│   ├── network.py       # UDP broadcast / descubrimiento de peers
│   ├── transfer.py      # Transferencia de archivos por TCP
│   └── tui.py           # Interfaz Textual (TUI)
├── scripts/
│   └── setup_batman.sh  # Configuración de batman-adv
├── requirements.txt
├── install.sh
└── README.md
```

---

## Historial y privacidad

- El historial se guarda en `~/.batman-chat/history.db` (SQLite)
- Los archivos recibidos se guardan en `~/batman-chat-files/` (configurable)
- Para borrar el historial: `rm ~/.batman-chat/history.db`
- La config está en `~/.batman-chat/config.json`

---

## Contribuir

1. Fork del repo
2. Crea una rama: `git checkout -b feature/mi-feature`
3. Commit: `git commit -m "feat: descripción"`
4. Push y abre un PR

---

## Licencia

MIT — úsalo, modifícalo, compártelo libremente.
