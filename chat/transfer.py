"""
transfer.py — Transferencia de archivos cifrados por TCP

Protocolo de transferencia:
  1. El emisor anuncia el archivo por UDP (network.py → FILE_ANNOUNCE).
  2. Cada peer receptor conecta al TCP server del emisor (puerto transfer_port).
  3. Handshake:
       [4 bytes big-endian = longitud del header cifrado]
       [N bytes = header JSON cifrado con Fernet]
       header = {"filename": str, "size": int, "sender": str}
  4. Datos:
       Mientras quedan bytes:
         [4 bytes big-endian = longitud del chunk cifrado]
         [M bytes = chunk cifrado]
     Cada chunk en claro tiene CHUNK_SIZE bytes (excepto el último).

El cifrado Fernet de cada chunk añade ~73 bytes de overhead por chunk,
lo cual es negligible para chunks de 64 KB.
"""

import asyncio
import json
from pathlib import Path
from typing import Callable, Optional

from .crypto import Crypto

CHUNK_SIZE = 65_536  # 64 KB por chunk


# ── Servidor de recepción ─────────────────────────────────────────────────────


class FileTransferServer:
    """
    Servidor TCP que acepta conexiones entrantes de peers
    y guarda los archivos recibidos en save_dir.
    """

    def __init__(
        self,
        crypto: Crypto,
        save_dir: str,
        port: int,
        on_file_received: Callable,
    ):
        self._crypto = crypto
        self._save_dir = Path(save_dir)
        self._save_dir.mkdir(parents=True, exist_ok=True)
        self._port = port
        self._on_file_received = on_file_received
        self._server: Optional[asyncio.AbstractServer] = None

    async def start(self) -> None:
        self._server = await asyncio.start_server(
            self._handle_connection,
            host="0.0.0.0",
            port=self._port,
        )
        asyncio.ensure_future(self._server.serve_forever())

    async def stop(self) -> None:
        if self._server:
            self._server.close()
            await self._server.wait_closed()

    async def _handle_connection(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        peer_ip = writer.get_extra_info("peername", ("?", 0))[0]
        try:
            # ── Leer header ────────────────────────────────────────────────
            header_len = int.from_bytes(await reader.readexactly(4), "big")
            header_enc = await reader.readexactly(header_len)
            header_raw = self._crypto.try_decrypt(header_enc)
            if header_raw is None:
                return
            header = json.loads(header_raw.decode("utf-8"))

            filename: str = header["filename"]
            total_size: int = header["size"]
            sender: str = header["sender"]

            # ── Evitar sobreescribir archivos existentes ───────────────────
            save_path = self._unique_path(filename)

            # ── Recibir chunks ─────────────────────────────────────────────
            received = 0
            with open(save_path, "wb") as f:
                while received < total_size:
                    chunk_len = int.from_bytes(await reader.readexactly(4), "big")
                    chunk_enc = await reader.readexactly(chunk_len)
                    chunk = self._crypto.try_decrypt(chunk_enc)
                    if chunk is None:
                        break
                    f.write(chunk)
                    received += len(chunk)

            # Notificar a la TUI
            await self._on_file_received(sender, filename, str(save_path))

        except (asyncio.IncompleteReadError, OSError, KeyError):
            pass
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    def _unique_path(self, filename: str) -> Path:
        """Genera una ruta que no sobreescriba archivos existentes."""
        path = self._save_dir / filename
        stem = Path(filename).stem
        suffix = Path(filename).suffix
        counter = 1
        while path.exists():
            path = self._save_dir / f"{stem}_{counter}{suffix}"
            counter += 1
        return path


# ── Cliente de envío ──────────────────────────────────────────────────────────


async def send_file(
    crypto: Crypto,
    filepath: str,
    sender: str,
    peer_ip: str,
    port: int,
    progress_callback: Optional[Callable] = None,
) -> None:
    """
    Envía un archivo cifrado a un peer por TCP.

    progress_callback(sent_bytes, total_bytes) se llama después de cada chunk.
    Levanta OSError / ConnectionRefusedError si el peer no está disponible.
    """
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"Archivo no encontrado: {filepath}")

    total_size = filepath.stat().st_size

    reader, writer = await asyncio.open_connection(peer_ip, port)

    try:
        # ── Enviar header ──────────────────────────────────────────────────
        header = json.dumps({
            "filename": filepath.name,
            "size": total_size,
            "sender": sender,
        }, ensure_ascii=False).encode("utf-8")

        header_enc = crypto.encrypt(header)
        writer.write(len(header_enc).to_bytes(4, "big") + header_enc)

        # ── Enviar chunks ──────────────────────────────────────────────────
        sent = 0
        with open(filepath, "rb") as f:
            while True:
                chunk = f.read(CHUNK_SIZE)
                if not chunk:
                    break
                chunk_enc = crypto.encrypt(chunk)
                writer.write(len(chunk_enc).to_bytes(4, "big") + chunk_enc)
                await writer.drain()
                sent += len(chunk)
                if progress_callback:
                    await progress_callback(sent, total_size)

        await writer.drain()

    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
