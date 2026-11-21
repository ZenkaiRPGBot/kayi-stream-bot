import math
import asyncio
import logging
import time
from typing import Dict, AsyncGenerator
from pyrogram import Client, raw
from pyrogram.file_id import FileId, FileType, ThumbnailSource
from pyrogram.session import Session, Auth
from pyrogram.errors import AuthBytesInvalid, FloodWait

logger = logging.getLogger("fast_streamer")

class FastByteStreamer:
    """
    High-Performance Zero-Disk MTProto Media Streamer.
    Maintains persistent warm media sessions across Telegram Data Centers (DCs),
    eliminating Diffie-Hellman handshake latency and session recreation overhead.
    """
    def __init__(self, client: Client):
        self.client: Client = client
        self.media_sessions: Dict[int, Session] = {}
        self.cached_file_ids: Dict[str, FileId] = {}
        self._lock = asyncio.Lock()
        self.chunk_size = 1024 * 1024  # 1 MiB standard chunk

    async def get_media_session(self, dc_id: int) -> Session:
        """
        Retrieves or initializes a persistent, authenticated media session for a given DC.
        Reuses active TCP sessions to achieve <50ms chunk response times.
        """
        if dc_id in self.media_sessions:
            return self.media_sessions[dc_id]

        async with self._lock:
            # Recheck inside lock
            if dc_id in self.media_sessions:
                return self.media_sessions[dc_id]

            logger.info(f"[FastStreamer] Initializing persistent media session for DC {dc_id}...")
            main_dc = await self.client.storage.dc_id()

            if dc_id != main_dc:
                # Cross-DC connection: Export authorization from main DC and import to media DC
                session = Session(
                    self.client,
                    dc_id,
                    await Auth(self.client, dc_id, await self.client.storage.test_mode()).create(),
                    await self.client.storage.test_mode(),
                    is_media=True,
                )
                await session.start()

                for attempt in range(6):
                    try:
                        exported_auth = await self.client.invoke(
                            raw.functions.auth.ExportAuthorization(dc_id=dc_id)
                        )
                        await session.invoke(
                            raw.functions.auth.ImportAuthorization(
                                id=exported_auth.id,
                                bytes=exported_auth.bytes
                            )
                        )
                        break
                    except AuthBytesInvalid:
                        logger.warning(f"[FastStreamer] AuthBytesInvalid on DC {dc_id}, retrying ({attempt + 1}/6)...")
                        await asyncio.sleep(0.3)
                else:
                    await session.stop()
                    raise AuthBytesInvalid(f"Failed to authorize media session for DC {dc_id}")
            else:
                # Same DC: Reuse main client's auth key
                session = Session(
                    self.client,
                    dc_id,
                    await self.client.storage.auth_key(),
                    await self.client.storage.test_mode(),
                    is_media=True,
                )
                await session.start()

            self.media_sessions[dc_id] = session
            logger.info(f"[FastStreamer] DC {dc_id} warm media session online and cached!")
            return session

    @staticmethod
    def get_input_location(file_id: FileId):
        """Builds MTProto InputFileLocation based on FileId specification."""
        file_type = file_id.file_type

        if file_type == FileType.CHAT_PHOTO:
            if file_id.chat_id > 0:
                peer = raw.types.InputPeerUser(
                    user_id=file_id.chat_id, access_hash=file_id.chat_access_hash
                )
            else:
                if file_id.chat_access_hash == 0:
                    peer = raw.types.InputPeerChat(chat_id=-file_id.chat_id)
                else:
                    peer = raw.types.InputPeerChannel(
                        channel_id=file_id.chat_id,
                        access_hash=file_id.chat_access_hash,
                    )
            return raw.types.InputPeerPhotoFileLocation(
                peer=peer,
                volume_id=file_id.volume_id,
                local_id=file_id.local_id,
                big=file_id.thumbnail_source == ThumbnailSource.CHAT_PHOTO_BIG,
            )
        elif file_type == FileType.PHOTO:
            return raw.types.InputPhotoFileLocation(
                id=file_id.media_id,
                access_hash=file_id.access_hash,
                file_reference=file_id.file_reference,
                thumb_size=file_id.thumbnail_size,
            )
        else:
            return raw.types.InputDocumentFileLocation(
                id=file_id.media_id,
                access_hash=file_id.access_hash,
                file_reference=file_id.file_reference,
                thumb_size=file_id.thumbnail_size,
            )

    async def yield_file(
        self,
        file_id_str: str,
        start_byte: int,
        content_length: int
    ) -> AsyncGenerator[bytes, None]:
        """
        Streams precise byte range chunk by chunk directly from Telegram servers.
        Correctly trims the first and last chunk to match HTTP Content-Length perfectly.
        """
        if file_id_str not in self.cached_file_ids:
            self.cached_file_ids[file_id_str] = FileId.decode(file_id_str)
        file_id = self.cached_file_ids[file_id_str]

        session = await self.get_media_session(file_id.dc_id)
        location = self.get_input_location(file_id)

        chunk_size = self.chunk_size
        end_byte = start_byte + content_length - 1

        offset = (start_byte // chunk_size) * chunk_size
        first_part_cut = start_byte % chunk_size
        last_part_cut = (end_byte % chunk_size) + 1
        part_count = math.ceil((end_byte - offset + 1) / chunk_size)

        current_part = 1
        while True:
            try:
                res = await session.invoke(
                    raw.functions.upload.GetFile(
                        location=location,
                        offset=offset,
                        limit=chunk_size
                    )
                )
            except FloodWait as fw:
                logger.warning(f"[FastStreamer] FloodWait: sleeping {fw.value}s")
                await asyncio.sleep(fw.value)
                continue
            except Exception as e:
                logger.error(f"[FastStreamer] RPC Error at offset {offset}: {e}")
                break

            if isinstance(res, raw.types.upload.File):
                chunk = res.bytes
                if not chunk:
                    break

                if part_count == 1:
                    yield chunk[first_part_cut:last_part_cut]
                elif current_part == 1:
                    yield chunk[first_part_cut:]
                elif current_part == part_count:
                    yield chunk[:last_part_cut]
                else:
                    yield chunk

                current_part += 1
                offset += chunk_size

                if current_part > part_count:
                    break
            else:
                break

    async def close(self):
        """Cleanly stops all warm media sessions."""
        for dc_id, session in list(self.media_sessions.items()):
            try:
                await session.stop()
            except Exception:
                pass
        self.media_sessions.clear()
