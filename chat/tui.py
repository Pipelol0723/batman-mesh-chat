"""
tui.py — Interfaz terminal con Textual para batman-mesh-chat

Layout:
  ┌─────────────────────────────────────────────┐
  │  🦇 batman-mesh-chat          [pipe@mesh]   │  ← Header (título + reloj)
  ├─────────────────────────────────────────────┤
  │                                             │
  │  [historial de mensajes — scrollable]       │  ← RichLog (1fr)
  │  pipe: hola a todos!                        │
  │  ana: hola pipe!                            │
  │  📎 carlos envió: foto.jpg (1.2 MB)        │
  │                                             │
  ├─────────────────────────────────────────────┤
  │  🔗 2 peer(s): ana, carlos | batman-mesh    │  ← barra de estado
  ├─────────────────────────────────────────────┤
  │  > _                                        │  ← Input
  └─────────────────────────────────────────────┘
  [F2 Archivo] [F5 Peers] [Ctrl+Q Salir]        ← Footer

Atajos de teclado:
  Enter    — enviar mensaje
  F2       — modo envío de archivo (pide ruta)
  F5       — listar peers en el log
  Ctrl+L   — limpiar pantalla (no borra DB)
  Ctrl+Q   — salir
"""

import asyncio
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.message import Message
from textual.widgets import Footer, Header, Input, Label, RichLog

from .config import save_config
from .crypto import Crypto
from .db import Database
from .network import NetworkManager
from .transfer import FileTransferServer, send_file

# ── Mensajes internos de Textual ─────────────────────────────────────────────


class IncomingMessage(Message):
    """Mensaje recibido desde la red → despachado al hilo de la TUI."""

    def __init__(self, msg: dict) -> None:
        super().__init__()
        self.msg = msg


# ── App principal ─────────────────────────────────────────────────────────────

PHOTO_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg", ".tiff"}


class BatmanChatApp(App):
    """Chat descentralizado para redes mesh con BATMAN-adv."""

    CSS = """
    Screen {
        background: $surface;
    }

    #chat-log {
        border: solid $primary;
        height: 1fr;
        padding: 0 1;
        scrollbar-gutter: stable;
    }

    #peers-bar {
        height: 1;
        background: $panel;
        color: $text-muted;
        content-align: left middle;
        padding: 0 1;
    }

    #msg-input {
        border: solid $accent;
        height: 3;
        margin: 0;
    }

    #msg-input:focus {
        border: solid $success;
    }
    """

    BINDINGS = [
        Binding("ctrl+q", "quit_app", "Salir", priority=True, show=True),
        Binding("f2", "send_file_mode", "Enviar Archivo", show=True),
        Binding("f5", "show_peers", "Ver Peers", show=True),
        Binding("ctrl+l", "clear_log", "Limpiar", show=False),
    ]

    def __init__(self, config: dict) -> None:
        super().__init__()
        self._config = config
        self._username = config["username"]
        self._crypto = Crypto(config["network_passphrase"])
        self._db = Database()
        self._network: Optional[NetworkManager] = None
        self._transfer_server: Optional[FileTransferServer] = None
        self._file_mode = False  # True cuando esperamos ruta de archivo

    # ── Composición de widgets ────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield RichLog(
            id="chat-log",
            markup=True,
            highlight=False,
            auto_scroll=True,
            wrap=True,
        )
        yield Label(
            f"🔗 Sin peers | Red: [bold]{self._config['network_passphrase']}[/bold]",
            id="peers-bar",
        )
        yield Input(
            placeholder="Escribe un mensaje... | F2: archivo | F5: peers | Ctrl+Q: salir",
            id="msg-input",
        )
        yield Footer()

    # ── Arranque ──────────────────────────────────────────────────────────

    async def on_mount(self) -> None:
        self.title = f"🦇 batman-mesh-chat — {self._username}"

        # Cargar historial
        log = self.query_one("#chat-log", RichLog)
        history = self._db.get_history(self._config.get("max_history", 100))
        if history:
            log.write("[dim]──────── historial ────────[/dim]")
            for msg in history:
                self._render_message(msg, from_history=True)
            log.write("[dim]──────── chat en vivo ─────[/dim]")

        # Servidor TCP para recibir archivos
        self._transfer_server = FileTransferServer(
            crypto=self._crypto,
            save_dir=self._config["save_dir"],
            port=self._config["transfer_port"],
            on_file_received=self._on_file_received,
        )
        await self._transfer_server.start()

        # Red UDP
        self._network = NetworkManager(
            crypto=self._crypto,
            username=self._username,
            msg_port=self._config["msg_port"],
            on_message=self._on_network_message,
        )
        await self._network.start()

        self._sys("Chat iniciado 🦇  Buscando peers en la red...")

    # ── Manejo de mensajes entrantes de la red ────────────────────────────

    async def _on_network_message(self, msg: dict) -> None:
        """Llamado desde asyncio (mismo loop que Textual). Postea al hilo UI."""
        self.post_message(IncomingMessage(msg))

    def on_incoming_message(self, event: IncomingMessage) -> None:
        """Handler de IncomingMessage en el hilo de la TUI."""
        msg = event.msg
        msg_type = msg.get("type", "text")
        sender = msg.get("sender", "?")
        content = msg.get("content", "")

        # Guardar en BD (no guardamos 'system' ni FILE_ANNOUNCE hasta completar)
        if msg_type == "MSG":
            self._db.save_message(
                sender=sender,
                msg_type="text",
                content=content,
                peer_ip=msg.get("peer_ip"),
            )
        elif msg_type == "FILE_ANNOUNCE":
            self._db.save_message(
                sender=sender,
                msg_type=msg.get("file_type", "file"),
                content=msg.get("filename", ""),
                filename=msg.get("filename"),
                peer_ip=msg.get("peer_ip"),
            )

        # Mostrar en pantalla
        msg["timestamp"] = datetime.now().isoformat(timespec="seconds")

        if msg_type == "MSG":
            msg["type"] = "text"

        self._render_message(msg)
        self._update_peers_bar()

        # Iniciar descarga automática de archivos anunciados
        if msg_type == "FILE_ANNOUNCE" and msg.get("peer_ip"):
            asyncio.create_task(self._auto_download(msg))

    # ── Descarga automática ───────────────────────────────────────────────

    async def _auto_download(self, msg: dict) -> None:
        peer_ip = msg["peer_ip"]
        filename = msg.get("filename", "archivo")
        port = msg.get("transfer_port", self._config["transfer_port"])
        sender = msg.get("sender", "?")

        try:
            from .transfer import FileTransferServer  # ya importado, solo para claridad

            # El servidor local ya escucha; necesitamos conectarnos al servidor
            # del peer emisor para descargar.
            # Reutilizamos la función de cliente send_file pero en modo "pull":
            # el protocolo es push-desde-emisor, así que solo necesitamos
            # que el servidor local lo acepte cuando el peer conecte.
            # → En nuestro protocolo el emisor conecta a cada peer,
            #   así que aquí solo mostramos la notificación cuando llega.
            self._sys(
                f"📥 {sender} está enviando [bold]{filename}[/bold] → "
                f"se guardará en {self._config['save_dir']}"
            )
        except Exception as e:
            self._sys(f"⚠ Error preparando descarga de {filename}: {e}")

    async def _on_file_received(
        self, sender: str, filename: str, save_path: str
    ) -> None:
        """Callback del FileTransferServer cuando completa una recepción."""
        self.post_message(IncomingMessage({
            "type": "file_done",
            "sender": sender,
            "filename": filename,
            "save_path": save_path,
        }))

    def on_incoming_message_file_done(self, _event) -> None:
        # No se usa; el handler genérico lo captura primero.
        pass

    # Sobrecargar el handler para capturar file_done:
    # (ya incluido en on_incoming_message arriba via msg_type == "file_done")

    # ── Input del usuario ─────────────────────────────────────────────────

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        inp = self.query_one("#msg-input", Input)
        inp.value = ""

        if not text:
            if self._file_mode:
                self._file_mode = False
                inp.placeholder = (
                    "Escribe un mensaje... | F2: archivo | F5: peers | Ctrl+Q: salir"
                )
                self._sys("❌ Envío de archivo cancelado.")
            return

        if self._file_mode:
            self._file_mode = False
            inp.placeholder = (
                "Escribe un mensaje... | F2: archivo | F5: peers | Ctrl+Q: salir"
            )
            await self._handle_file_send(text)
        else:
            await self._handle_text_send(text)

    async def _handle_text_send(self, text: str) -> None:
        """Envía un mensaje de texto por broadcast."""
        if not self._network:
            return
        await self._network.send_message(text)
        self._db.save_message(sender=self._username, msg_type="text", content=text)
        self._render_message({
            "type": "text",
            "sender": self._username,
            "content": text,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        })

    async def _handle_file_send(self, filepath: str) -> None:
        """Envía un archivo a todos los peers conectados."""
        if not self._network:
            return

        filepath = filepath.strip()
        if not os.path.exists(filepath):
            self._sys(f"❌ Archivo no encontrado: [bold]{filepath}[/bold]")
            return

        peers = self._network.get_peers()
        if not peers:
            self._sys("❌ No hay peers conectados en la red.")
            return

        filename = os.path.basename(filepath)
        file_size = os.path.getsize(filepath)
        ext = Path(filename).suffix.lower()
        file_type = "photo" if ext in PHOTO_EXTS else "file"

        self._sys(
            f"📤 Enviando [bold]{filename}[/bold] "
            f"({_fmt_size(file_size)}) a {len(peers)} peer(s)..."
        )

        # Anunciar por UDP
        await self._network.announce_file(filename, file_size, file_type)

        # Enviar por TCP a cada peer
        errors = []
        for peer_ip, peer_name in list(peers.items()):
            try:
                await send_file(
                    self._crypto,
                    filepath,
                    self._username,
                    peer_ip,
                    self._config["transfer_port"],
                )
            except Exception as e:
                errors.append(f"{peer_name} ({peer_ip}): {e}")

        if errors:
            self._sys(f"⚠ Errores: {' | '.join(errors)}")
        else:
            self._sys(f"✅ [bold]{filename}[/bold] enviado correctamente.")

        self._db.save_message(
            sender=self._username,
            msg_type=file_type,
            content=filepath,
            filename=filename,
        )

    # ── Acciones de teclado ───────────────────────────────────────────────

    def action_send_file_mode(self) -> None:
        """F2 — activa el modo de envío de archivo."""
        self._file_mode = True
        inp = self.query_one("#msg-input", Input)
        inp.placeholder = "Ruta completa del archivo (ej: /home/pipe/foto.jpg) — Enter para enviar, vacío para cancelar"
        inp.focus()
        self._sys("📁 Escribe la ruta del archivo y presiona Enter.")

    def action_show_peers(self) -> None:
        """F5 — muestra peers en el log."""
        if not self._network:
            return
        peers = self._network.get_peers()
        if peers:
            lines = " | ".join(f"[bold]{v}[/bold] ({k})" for k, v in peers.items())
            self._sys(f"👥 {len(peers)} peer(s): {lines}")
        else:
            self._sys("👥 Sin peers en la red. ¿Está batman-adv activo?")

    def action_clear_log(self) -> None:
        """Ctrl+L — limpia la pantalla (el historial en SQLite se conserva)."""
        log = self.query_one("#chat-log", RichLog)
        log.clear()
        self._sys("🧹 Pantalla limpiada. El historial en disco sigue intacto.")

    async def action_quit_app(self) -> None:
        """Ctrl+Q — salida limpia."""
        if self._network:
            await self._network.stop()
        if self._transfer_server:
            await self._transfer_server.stop()
        self._db.close()
        self.exit()

    # ── Renderizado ───────────────────────────────────────────────────────

    def _render_message(self, msg: dict, from_history: bool = False) -> None:
        log = self.query_one("#chat-log", RichLog)
        msg_type = msg.get("type", "text")
        sender = msg.get("sender", "?")
        content = msg.get("content", "")
        ts = _fmt_ts(msg.get("timestamp", ""))

        if msg_type == "system":
            log.write(f"[dim]{ts} ⚡ {content}[/dim]")

        elif msg_type == "file_done":
            filename = msg.get("filename", "?")
            save_path = msg.get("save_path", "")
            log.write(
                f"[dim]{ts}[/dim] [green]✅ Archivo de [bold]{sender}[/bold]: "
                f"[bold]{filename}[/bold] → {save_path}[/green]"
            )

        elif msg_type in ("file", "photo", "FILE_ANNOUNCE"):
            filename = msg.get("filename", content)
            icon = "🖼 " if msg_type == "photo" else "📎"
            size_str = _fmt_size(msg.get("size", 0)) if msg.get("size") else ""
            size_part = f" ({size_str})" if size_str else ""
            if sender == self._username:
                log.write(
                    f"[dim]{ts}[/dim] [bold green]{sender}[/bold green] "
                    f"{icon} [cyan]{filename}{size_part}[/cyan]"
                )
            else:
                log.write(
                    f"[dim]{ts}[/dim] [bold yellow]{sender}[/bold yellow] "
                    f"envió {icon} [cyan]{filename}{size_part}[/cyan]"
                )

        else:
            # Mensaje de texto
            dim = "[dim]" if from_history else ""
            dim_end = "[/dim]" if from_history else ""
            if sender == self._username:
                log.write(
                    f"{dim}[dim]{ts}[/dim] "
                    f"[bold green]{sender}[/bold green]: {content}{dim_end}"
                )
            else:
                log.write(
                    f"{dim}[dim]{ts}[/dim] "
                    f"[bold yellow]{sender}[/bold yellow]: {content}{dim_end}"
                )

    def _sys(self, text: str) -> None:
        """Muestra un mensaje de sistema en el log."""
        self._render_message({
            "type": "system",
            "sender": "Sistema",
            "content": text,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        })

    def _update_peers_bar(self) -> None:
        if not self._network:
            return
        peers = self._network.get_peers()
        label = self.query_one("#peers-bar", Label)
        net = self._config["network_passphrase"]
        if peers:
            names = ", ".join(peers.values())
            label.update(
                f"🔗 [bold]{len(peers)}[/bold] peer(s): {names} | Red: [bold]{net}[/bold]"
            )
        else:
            label.update(f"🔗 Sin peers | Red: [bold]{net}[/bold]")


# ── Utilidades ────────────────────────────────────────────────────────────────


def _fmt_ts(ts: str) -> str:
    """Extrae HH:MM de un ISO timestamp."""
    if len(ts) >= 16:
        return ts[11:16]
    return ts


def _fmt_size(size: int) -> str:
    """Formatea bytes en unidad legible."""
    if size < 1024:
        return f"{size} B"
    if size < 1024 ** 2:
        return f"{size / 1024:.1f} KB"
    if size < 1024 ** 3:
        return f"{size / 1024 ** 2:.1f} MB"
    return f"{size / 1024 ** 3:.1f} GB"
