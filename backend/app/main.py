"""The FastAPI app. It serves the documents and the scripts, the /ws WebSocket, and the built
frontend. So the full demo runs as one process."""

import json

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import TypeAdapter, ValidationError

from . import config, docs, rooms
from .docs import DocLine
from .models import ClientMessage, ErrorMessage, Join

app = FastAPI(title="Beacon")
parse_message = TypeAdapter(ClientMessage).validate_json


@app.get("/api/documents")
def get_documents() -> list[DocLine]:
    return list(docs.LINES.values())


@app.get("/api/scripts/{name}")
def get_script(name: str) -> list[dict]:
    available = {path.stem for path in config.SCRIPTS_DIR.glob("*.json")}
    if name not in available:
        raise HTTPException(404, f"No script named {name!r}. Available: {sorted(available)}")
    return json.loads((config.SCRIPTS_DIR / f"{name}.json").read_text(encoding="utf-8"))


@app.websocket("/ws")
async def websocket(ws: WebSocket) -> None:
    await ws.accept()
    try:
        join = parse_message(await ws.receive_text())
    except (ValidationError, WebSocketDisconnect):
        await ws.close(code=1008)
        return
    if not isinstance(join, Join):
        await ws.close(code=1008)
        return
    room = rooms.get_room(join.room)
    await rooms.connect(room, ws, join.role)
    try:
        while True:
            raw = await ws.receive_text()
            try:
                message = parse_message(raw)
            except ValidationError as exc:
                await ws.send_text(ErrorMessage(message=f"bad message: {exc.errors()[0]['msg']}").model_dump_json())
                continue
            await rooms.handle(room, ws, join.role, message)
    except WebSocketDisconnect:
        pass
    finally:  # for all ends of the connection: release the tab's push-to-talk, and stop sending to it
        await rooms.disconnect(room, ws)


@app.get("/{path:path}", include_in_schema=False)
def frontend(path: str):
    """Serve the built React app. Other paths (/call, /observer) get index.html."""
    if path.startswith("api/"):
        raise HTTPException(404, f"No API route /{path}")
    dist = config.WEB_DIST.resolve()
    file = (dist / path).resolve()
    if path and file.is_file() and file.is_relative_to(dist):
        return FileResponse(file)
    if (dist / "index.html").is_file():
        return FileResponse(dist / "index.html")
    return PlainTextResponse("Frontend not built yet: run `python tasks.py build`, or use the dev server.", 404)
