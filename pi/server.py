#!/usr/bin/env python3
"""
Romi iPad control server.

Serves a touch-friendly web UI and relays commands to the Romi 32U4
over I2C. Uses WebSocket for low-latency drive and arm control.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from romi_bridge import I2CNotAvailableError, RomiBridge

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("romi-server")

STATIC_DIR = Path(__file__).resolve().parent / "static"
COMMAND_TIMEOUT_S = 0.5
STATUS_INTERVAL_S = 0.25

romi: RomiBridge | None = None
last_command_time = 0.0
current_servos = (90, 90, 45)
current_motors = (0, 0)
i2c_unavailable_logged = False


def get_romi() -> RomiBridge:
    global romi
    if romi is None:
        romi = RomiBridge()
    return romi


def log_i2c_error(exc: OSError, context: str) -> None:
    global i2c_unavailable_logged
    if isinstance(exc, I2CNotAvailableError) or "No such file or directory" in str(exc):
        if not i2c_unavailable_logged:
            logger.error("%s: %s", context, exc)
            i2c_unavailable_logged = True
        return
    logger.warning("%s: %s", context, exc)


async def watchdog_loop() -> None:
    """Stop motors if no commands arrive within the timeout window."""
    global last_command_time
    while True:
        await asyncio.sleep(0.1)
        if time.monotonic() - last_command_time > COMMAND_TIMEOUT_S:
            try:
                get_romi().stop_motors()
            except OSError as exc:
                log_i2c_error(exc, "Watchdog I2C error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        get_romi()
        logger.info("I2C connected on /dev/i2c-%s", romi.bus_number)
    except I2CNotAvailableError as exc:
        logger.error("%s", exc)

    task = asyncio.create_task(watchdog_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    try:
        get_romi().stop_motors()
    except OSError:
        pass


app = FastAPI(title="Romi iPad Control", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/status")
async def status() -> dict:
    bridge = get_romi()
    data = bridge.read_status()
    return {
        "buttons": data.buttons,
        "battery_millivolts": data.battery_millivolts,
        "analog": data.analog,
        "encoders": data.encoders,
        "servos": data.servos,
        "motors": current_motors,
    }


def apply_command(payload: dict) -> dict:
    global last_command_time, current_servos, current_motors
    last_command_time = time.monotonic()
    bridge = get_romi()
    response: dict = {"ok": True}

    if payload.get("type") == "drive":
        left = int(payload.get("left", 0))
        right = int(payload.get("right", 0))
        bridge.set_motors(left, right)
        current_motors = (left, right)
        response["motors"] = current_motors

    elif payload.get("type") == "servos":
        a2 = int(payload.get("a2", current_servos[0]))
        a3 = int(payload.get("a3", current_servos[1]))
        a4 = int(payload.get("a4", current_servos[2]))
        bridge.set_servos(a2, a3, a4)
        current_servos = (a2, a3, a4)
        response["servos"] = current_servos

    elif payload.get("type") == "preset":
        preset = payload.get("name", "")
        presets = {
            "home": (90, 90, 45),
            "reach": (90, 45, 90),
            "grip_open": (current_servos[0], current_servos[1], 120),
            "grip_close": (current_servos[0], current_servos[1], 30),
        }
        if preset in presets:
            current_servos = presets[preset]
            bridge.set_servos(*current_servos)
            response["servos"] = current_servos
        else:
            response["ok"] = False
            response["error"] = f"Unknown preset: {preset}"

    elif payload.get("type") == "stop":
        bridge.stop_motors()
        current_motors = (0, 0)
        response["motors"] = current_motors

    elif payload.get("type") == "estop":
        bridge.stop_motors()
        current_motors = (0, 0)
        response["motors"] = current_motors

    else:
        response["ok"] = False
        response["error"] = f"Unknown command type: {payload.get('type')}"

    return response


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    bridge = get_romi()
    try:
        while True:
            receive_task = asyncio.create_task(websocket.receive_text())
            status_task = asyncio.create_task(asyncio.sleep(STATUS_INTERVAL_S))
            done, pending = await asyncio.wait(
                {receive_task, status_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()

            if receive_task in done:
                raw = receive_task.result()
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError:
                    await websocket.send_json({"ok": False, "error": "Invalid JSON"})
                    continue

                if payload.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
                    continue

                try:
                    result = await asyncio.to_thread(apply_command, payload)
                    await websocket.send_json(result)
                except OSError as exc:
                    await websocket.send_json({"ok": False, "error": str(exc)})

            if status_task in done:
                try:
                    data = await asyncio.to_thread(bridge.read_status)
                    await websocket.send_json(
                        {
                            "type": "status",
                            "battery_millivolts": data.battery_millivolts,
                            "buttons": data.buttons,
                            "encoders": data.encoders,
                            "servos": data.servos,
                            "motors": current_motors,
                        }
                    )
                except OSError as exc:
                    await websocket.send_json({"type": "status", "error": str(exc)})

    except WebSocketDisconnect:
        logger.info("Client disconnected")
    finally:
        try:
            bridge.stop_motors()
        except OSError:
            pass


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)
