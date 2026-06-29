"""
I2C bridge between Raspberry Pi and Romi 32U4 control board.

Extends the Pololu a_star.py protocol with arm/gripper servo control.
Buffer layout must match firmware/RomiArmGripper/RomiArmGripper.ino.
"""

from __future__ import annotations

import struct
import time
from dataclasses import dataclass

import smbus2 as smbus

I2C_ADDRESS = 20
I2C_DELAY_S = 0.0001

# Buffer offsets (bytes)
OFFSET_LEDS = 0
OFFSET_BUTTONS = 3
OFFSET_MOTORS = 6
OFFSET_BATTERY = 10
OFFSET_ANALOG = 12
OFFSET_PLAY_NOTES = 24
OFFSET_ENCODERS = 39
OFFSET_SERVO_A2 = 43
OFFSET_SERVO_A3 = 44
OFFSET_SERVO_A4 = 45


@dataclass(frozen=True)
class RomiStatus:
    buttons: tuple[bool, bool, bool]
    battery_millivolts: int
    analog: tuple[int, int, int, int, int, int]
    encoders: tuple[int, int]
    servos: tuple[int, int, int]


class RomiBridge:
    """Communicates with Romi 32U4 firmware over I2C."""

    def __init__(self, bus_number: int = 1, address: int = I2C_ADDRESS) -> None:
        self.bus = smbus.SMBus(bus_number)
        self.address = address

    def _read_block(self, address: int, size: int) -> bytes:
        self.bus.write_byte(self.address, address)
        time.sleep(I2C_DELAY_S)
        return bytes(self.bus.read_byte(self.address) for _ in range(size))

    def _write_block(self, address: int, data: bytes) -> None:
        self.bus.write_i2c_block_data(self.address, address, list(data))
        time.sleep(I2C_DELAY_S)

    def read_unpack(self, address: int, size: int, fmt: str):
        return struct.unpack(fmt, self._read_block(address, size))

    def write_pack(self, address: int, fmt: str, *data) -> None:
        self._write_block(address, struct.pack(fmt, *data))

    def set_leds(self, red: bool, yellow: bool, green: bool) -> None:
        self.write_pack(OFFSET_LEDS, "BBB", int(red), int(yellow), int(green))

    def set_motors(self, left: int, right: int) -> None:
        left = max(-400, min(400, int(left)))
        right = max(-400, min(400, int(right)))
        self.write_pack(OFFSET_MOTORS, "hh", left, right)

    def stop_motors(self) -> None:
        self.set_motors(0, 0)

    def set_servos(self, a2: int, a3: int, a4: int) -> None:
        """Set arm servo angles (0-180 degrees) for pins A2, A3, A4."""
        angles = tuple(max(0, min(180, int(angle))) for angle in (a2, a3, a4))
        self.write_pack(OFFSET_SERVO_A2, "BBB", *angles)

    def set_servo(self, index: int, angle: int) -> None:
        offsets = (OFFSET_SERVO_A2, OFFSET_SERVO_A3, OFFSET_SERVO_A4)
        if index not in (0, 1, 2):
            raise ValueError("Servo index must be 0 (A2), 1 (A3), or 2 (A4)")
        angle = max(0, min(180, int(angle)))
        self.write_pack(offsets[index], "B", angle)

    def play_notes(self, notes: str) -> None:
        self.write_pack(OFFSET_PLAY_NOTES, "B14s", 1, notes.encode("ascii"))

    def read_status(self) -> RomiStatus:
        buttons = self.read_unpack(OFFSET_BUTTONS, 3, "???")
        battery_millivolts = self.read_unpack(OFFSET_BATTERY, 2, "H")[0]
        analog = self.read_unpack(OFFSET_ANALOG, 12, "HHHHHH")
        encoders = self.read_unpack(OFFSET_ENCODERS, 4, "hh")
        servos = self.read_unpack(OFFSET_SERVO_A2, 3, "BBB")
        return RomiStatus(
            buttons=buttons,
            battery_millivolts=battery_millivolts,
            analog=analog,
            encoders=encoders,
            servos=servos,
        )

    def read_buttons(self) -> tuple[bool, bool, bool]:
        return self.read_unpack(OFFSET_BUTTONS, 3, "???")

    def read_battery_millivolts(self) -> int:
        return self.read_unpack(OFFSET_BATTERY, 2, "H")[0]

    def read_encoders(self) -> tuple[int, int]:
        return self.read_unpack(OFFSET_ENCODERS, 4, "hh")
