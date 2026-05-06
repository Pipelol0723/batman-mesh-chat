"""
network.py — Capa de red UDP para batman-mesh-chat

Protocolo:
  • Cada paquete UDP es un JSON cifrado con Fernet.
  • Se envía por broadcast (255.255.255.255) al puerto msg_port.
  • BATMAN-adv propaga el broadcast por toda la malla a nivel L2.

Tipos de mensaje (campo "type"):
  DISCOVER      — "Acabo de entrar, estoy aquí" (se responde con HEARTBEAT)
  HEARTBEAT     — Latido periódico (cada 30 s) para mantener lista de peers
  LEAVE         — Salida limpia
  MSG           — Mensaje de texto
  FILE_ANNOUNCE — Notificación de archivo disponible para descargar
"""

import asyncio
import json
import socket
from typing import Callable, Dict, Optional

from .crypto import Crypto


# ── Protocolo UDP ────────────────────────────────────────────────────────────


class _UDPProtocol(asyncio.DatagramProtocol):
    """Protocolo asyncio para recibir datagramas UDP cifrados."""

    def __init__(self, handler: Callable):
        self._handler = handler
        self.transport: Optional[asyncio.DatagramTransport] = None

    def connection_made(self, transport: asyncio.DatagramTransport) -> None:
        self.transport = transport

    def datagram_received(self, data: bytes, addr: tuple) -> None:
        ip = addr[0]
        asyncio.ensure_future(self._handler(data, ip))

    def error_received(self, exc: Exception) -> None:
        pass  # ignorar errores de red transitorios

    def connection_lost(self, exc: Exception) -> None:
        pass

    def send(self, data: bytes, addr: tuple) -> None:
        if self.transport:
            self.transport.sendto(data, addr)


# ── NetworkManager ───────────────────────────────────────────────────────────


class NetworkManager:
    """
    Gestiona el descubrimiento de peers y el envío/recepción de mensajes
    por UDP broadcast.

    Parámetros:
        crypto       — instancia de Crypto con la clave de red
        username     — nombre del usuario local
        msg_port     — puerto UDP (default 9999)
        on_message   — coroutine async llamada al recibir cualquier mensaje
                       con firma:  async def cb(msg: dict) -> None
    """

    HEARTBEAT_INTERVAL = 30  # segundos

    def __init__(
        self,
        crypto: Crypto,
        username: str,
        msg_port: int,
        on_message: Callable,
    ):
        self._crypto = crypto
        self._username = username
        self._port = msg_port
        self._on_message = on_message

        self._peers: Dict[str, str] = {}  # ip → username
        self._protocol: Optional[_UDPProtocol] = None
        self._running = False
        self._tasks: list = []

    # ── Ciclo de vida ─────────────────────────────────────────────────────

    async def start(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.bind(("", self._port))
        sock.setblocking(False)

        loop = asyncio.get_running_loop()
        transport, protocol = await loop.create_datagram_endpoint(
            lambda: _UDPProtocol(self._handle_raw),
            sock=sock,
        )
        self._protocol = protocol
        self._running = True

        # Anunciar presencia
        await self._send_raw({"type": "DISCOVER", "sender": self._username})

        # Latido periódico
        t = asyncio.create_task(self._heartbeat_loop())
        self._tasks.append(t)

    async def stop(self) -> None:
        self._running = False
        for t in self._tasks:
            t.cancel()
        await self._send_raw({"type": "LEAVE", "sender": self._username})
        if self._protocol and self._protocol.transport:
            self._protocol.transport.close()

    # ── Envío ──────────────────────────────────────────────────────────────

    async def send_message(self, text: str) -> None:
        await self._send_raw({
            "type": "MSG",
            "sender": self._username,
            "content": text,
        })

    async def announce_file(
        self, filename: str, size: int, file_type: str = "file"
    ) -> None:
        """
        Anuncia por broadcast que hay un archivo disponible.
        Los peers conectarán al TCP server para descargarlo.
        """
        await self._send_raw({
            "type": "FILE_ANNOUNCE",
            "sender": self._username,
            "filename": filename,
            "size": size,
            "file_type": file_type,   # 'file' | 'photo'
            "transfer_port": 9998,    # peers usarán esta info
        })

    # ── Recepción ─────────────────────────────────────────────────────────

    async def _handle_raw(self, data: bytes, ip: str) -> None:
        """Descifra y despacha un datagrama entrante."""
        raw = self._crypto.try_decrypt(data)
        if raw is None:
            return  # paquete de otra red o corrupto

        try:
            msg: dict = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return

        await self._dispatch(msg, ip)

    async def _dispatch(self, msg: dict, ip: str) -> None:
        t = msg.get("type", "")
        sender = msg.get("sender", "desconocido")

        if t == "DISCOVER":
            was_new = ip not in self._peers
            self._peers[ip] = sender
            # Responder con nuestro heartbeat para que el recién llegado nos vea
            await self._send_raw({"type": "HEARTBEAT", "sender": self._username})
            if was_new:
                await self._on_message({
                    "type": "system",
                    "sender": "Sistema",
                    "content": f"👋 {sender} se unió a la red",
                })

        elif t == "HEARTBEAT":
            self._peers[ip] = sender

        elif t == "LEAVE":
            self._peers.pop(ip, None)
            await self._on_message({
                "type": "system",
                "sender": "Sistema",
                "content": f"🚪 {sender} dejó la red",
            })

        elif t == "MSG":
            if sender != self._username:
                await self._on_message(msg)

        elif t == "FILE_ANNOUNCE":
            # Añadir IP del peer para que la TUI pueda iniciar la descarga
            msg["peer_ip"] = ip
            await self._on_message(msg)

    # ── Helpers ────────────────────────────────────────────────────────────

    async def _send_raw(self, msg: dict) -> None:
        if not self._protocol:
            return
        data = self._crypto.encrypt(json.dumps(msg, ensure_ascii=False).encode("utf-8"))
        self._protocol.send(data, ("255.255.255.255", self._port))

    async def _heartbeat_loop(self) -> None:
        while self._running:
            await asyncio.sleep(self.HEARTBEAT_INTERVAL)
            await self._send_raw({"type": "HEARTBEAT", "sender": self._username})

    # ── Consultas ─────────────────────────────────────────────────────────

    def get_peers(self) -> Dict[str, str]:
        """Retorna copia del dict {ip: username} de peers conocidos."""
        return dict(self._peers)
