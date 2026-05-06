# 🦇 batman-mesh-chat

Chat descentralizado para redes mesh Linux usando [BATMAN-adv](https://www.open-mesh.org/projects/batman-adv/wiki).

- **Sin servidor central** — mensajes por broadcast UDP cifrado en la malla
- **Descubrimiento automático** de peers en la red
- **Mensajes de texto** con historial SQLite local
- **Envío de archivos y fotos** cifrados por TCP
- **Cifrado Fernet** (AES-128-CBC + HMAC-SHA256) con clave derivada de passphrase
- **TUI con Textual** — interfaz de terminal moderna y responsiva

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

## Instalación y primer uso

```bash
git clone https://github.com/Pipelol0723/batman-mesh-chat
cd batman-mesh-chat
bash install.sh
```

### Requisitos

- Linux (Ubuntu 20.04+ / Debian 11+ / cualquier distro con Python 3.10+)
- Python 3.10 o superior
- Tarjeta WiFi con soporte **IBSS/ad-hoc** (verificar con `iw list | grep IBSS`)
- `batctl` e `iw` (el script los instala automáticamente)

---

## Uso rápido — un solo comando

```bash
# Detecta la interfaz WiFi automáticamente
sudo bash start.sh

# O especifica la interfaz manualmente
sudo bash start.sh wlan0
```

Este script hace todo en orden:
1. Detecta la interfaz WiFi
2. Configura batman-adv si no está activo
3. Corrige el broadcast de bat0 si es necesario
4. Arranca el chat

### Primer arranque

Al ejecutar por primera vez pedirá:
- **Nombre de usuario** (sin espacios, máx 20 caracteres)
- **Contraseña de red** (debe ser igual en todos los nodos; default: `batman-mesh`)

La config se guarda en `~/.batman-chat/config.json` y no vuelve a pedirse.

---

## Opciones de línea de comandos

```bash
python3 batman_chat.py --user TuNombre       # establece nombre de usuario
python3 batman_chat.py --passphrase mi-red   # cambia la contraseña de red
python3 batman_chat.py --info                # muestra la config actual
python3 batman_chat.py --reset               # borra config y reconfigura
```

---

## Atajos de teclado en la TUI

| Tecla    | Acción                                    |
|----------|-------------------------------------------|
| `Enter`  | Enviar mensaje                            |
| `F2`     | Modo envío de archivo (pide ruta)         |
| `F5`     | Mostrar peers conectados en el log        |
| `Ctrl+L` | Limpiar pantalla (historial en DB intacto)|
| `Ctrl+Q` | Salir limpiamente                         |

---

## Setup manual de red mesh con BATMAN-adv

Si prefieres configurar la red manualmente en lugar de usar `start.sh`:

```bash
# 1. Configurar batman-adv (reemplaza wlan0 con tu interfaz)
sudo bash scripts/setup_batman.sh wlan0

# 2. Arrancar el chat
python3 batman_chat.py
```

### Verificar conectividad entre nodos

```bash
sudo batctl n          # peers batman-adv visibles
sudo batctl t          # tabla de enrutamiento completa
ping <IP_del_peer>     # prueba de conectividad (IPs en 10.20.30.X)
```

### Volver a WiFi normal

```bash
sudo systemctl restart NetworkManager
```

---

## Conectar múltiples nodos

Todos los nodos deben:
1. Tener instalado batman-mesh-chat (`git clone` + `bash install.sh`)
2. Ejecutar `sudo bash start.sh` con su propia interfaz WiFi
3. Usar la **misma `network_passphrase`** en `~/.batman-chat/config.json`
4. Estar en **rango físico** de al menos un nodo de la malla

No hay nodo central — cualquier nodo puede entrar o salir sin afectar al resto.

---

## Cifrado

| Componente          | Algoritmo / Parámetros                    |
|---------------------|-------------------------------------------|
| Derivación de clave | PBKDF2-HMAC-SHA256, 100 000 iteraciones   |
| Cifrado mensajes    | Fernet (AES-128-CBC + HMAC-SHA256)        |
| Cifrado archivos    | Fernet por chunks de 64 KB               |
| Salt                | Fijo por red (`batman-mesh-salt-v1`)      |
| Transporte          | UDP broadcast (mensajes) + TCP (archivos) |

Solo los nodos con la misma passphrase pueden leer los mensajes. Un observador con Wireshark solo verá bytes cifrados.

---

## Estructura del proyecto

```
batman-mesh-chat/
├── batman_chat.py        # Punto de entrada + CLI
├── start.sh              # Script de inicio todo-en-uno
├── install.sh            # Instalador de dependencias
├── chat/
│   ├── config.py         # Config ~/.batman-chat/config.json
│   ├── crypto.py         # Cifrado Fernet (PBKDF2 + AES)
│   ├── db.py             # Historial SQLite (~/.batman-chat/history.db)
│   ├── network.py        # UDP broadcast / descubrimiento de peers
│   ├── transfer.py       # Transferencia de archivos por TCP
│   └── tui.py            # Interfaz Textual (TUI)
├── scripts/
│   └── setup_batman.sh   # Configuración de batman-adv
└── requirements.txt
```

---

## Historial y privacidad

- Historial en `~/.batman-chat/history.db` (SQLite local)
- Archivos recibidos en `~/batman-chat-files/` (configurable)
- Para borrar historial: `rm ~/.batman-chat/history.db`
- Para resetear config: `python3 batman_chat.py --reset`

---

## Contribuir

1. Fork del repo
2. Crea una rama: `git checkout -b feature/mi-feature`
3. Commit: `git commit -m "feat: descripción"`
4. Push y abre un PR

---

## Licencia

MIT — úsalo, modifícalo, compártelo libremente.
