from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

_MAX_MESSAGE_LEN = 500


class ChatRoom:
    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._usernames: dict[WebSocket, str] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._clients.add(websocket)
            self._usernames[websocket] = "anon"

    async def disconnect(self, websocket: WebSocket) -> str:
        async with self._lock:
            username = self._usernames.get(websocket, "anon")
            self._clients.discard(websocket)
            self._usernames.pop(websocket, None)
            return username

    async def rename(self, websocket: WebSocket, username: str) -> str:
        safe_name = username.strip()[:24] or "anon"
        async with self._lock:
            self._usernames[websocket] = safe_name
            return safe_name

    async def connection_count(self) -> int:
        async with self._lock:
            return len(self._clients)

    async def username_for(self, websocket: WebSocket) -> str:
        async with self._lock:
            return self._usernames.get(websocket, "anon")

    async def broadcast(self, payload: dict[str, object]) -> None:
        async with self._lock:
            clients = list(self._clients)

        failed_clients: list[WebSocket] = []
        for client in clients:
            try:
                await client.send_json(payload)
            except Exception:
                failed_clients.append(client)

        if not failed_clients:
            return

        async with self._lock:
            for client in failed_clients:
                self._clients.discard(client)
                self._usernames.pop(client, None)


_chat_room = ChatRoom()


def _timestamp() -> str:
    return datetime.now(UTC).isoformat()


@router.websocket("/ws/chat")
async def ws_chat(websocket: WebSocket) -> None:
    await _chat_room.connect(websocket)
    joined_as = await _chat_room.username_for(websocket)
    current_connections = await _chat_room.connection_count()
    await _chat_room.broadcast(
        {
            "type": "system",
            "message": f"{joined_as} joined the chat.",
            "timestamp": _timestamp(),
            "user_count": current_connections,
        }
    )

    try:
        while True:
            payload = await websocket.receive_json()
            message_type = str(payload.get("type", ""))

            if message_type == "join":
                requested_username = str(payload.get("username", ""))
                username = await _chat_room.rename(websocket, requested_username)
                current_connections = await _chat_room.connection_count()
                await _chat_room.broadcast(
                    {
                        "type": "system",
                        "message": f"{username} is now online.",
                        "timestamp": _timestamp(),
                        "user_count": current_connections,
                    }
                )
                continue

            if message_type != "chat_message":
                await websocket.send_json({"type": "error", "message": "Unsupported event type."})
                continue

            text = str(payload.get("message", "")).strip()
            if not text:
                await websocket.send_json({"type": "error", "message": "Message cannot be empty."})
                continue
            if len(text) > _MAX_MESSAGE_LEN:
                await websocket.send_json(
                    {"type": "error", "message": f"Message exceeds {_MAX_MESSAGE_LEN} characters."}
                )
                continue

            username = await _chat_room.username_for(websocket)
            await _chat_room.broadcast(
                {
                    "type": "chat_message",
                    "username": username,
                    "message": text,
                    "timestamp": _timestamp(),
                }
            )
    except WebSocketDisconnect:
        pass
    except Exception:
        await websocket.close(code=1011)
    finally:
        username = await _chat_room.disconnect(websocket)
        current_connections = await _chat_room.connection_count()
        await _chat_room.broadcast(
            {
                "type": "system",
                "message": f"{username} left the chat.",
                "timestamp": _timestamp(),
                "user_count": current_connections,
            }
        )
