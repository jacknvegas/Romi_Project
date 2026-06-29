# Romi Project

Python 3 control software for a Pololu Romi robot with arm/gripper, controlled from an Apple iPad over WiFi.

## Architecture

```
iPad (Safari)  ──WiFi──►  Raspberry Pi 5 (Python/FastAPI)  ──I2C──►  Romi 32U4 (Arduino)
                                                              │
                                                         Motors + 3 Servos
                                                         (pins 20, 21, 22)
```

| Layer | Technology | Purpose |
|-------|------------|---------|
| iPad | Web browser | Touch joystick, arm sliders, presets |
| Raspberry Pi 5 | Python 3, FastAPI, WebSocket | Web server, I2C master |
| Romi 32U4 | Arduino (C++) | Motor PWM, servo control, sensors |

## Arm Servo Wiring

| Servo | Arduino Pin | Analog Label | Function |
|-------|-------------|--------------|----------|
| Base | 20 | A2 | Arm rotation |
| Shoulder | 21 | A3 | Arm lift |
| Gripper | 22 | A4 | Open/close |

## Quick Start

### 1. Upload firmware to Romi 32U4

Open `firmware/RomiArmGripper/RomiArmGripper.ino` in Arduino IDE and upload. See [docs/setup.md](docs/setup.md) for library installation and Servo Timer3 configuration.

### 2. Run the Python server on Raspberry Pi

```bash
cd pi
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python3 server.py
```

### 3. Control from iPad

Connect iPad and Pi to the same WiFi network, then open:

```
http://<raspberry-pi-ip>:8000
```

## Project Structure

```
firmware/RomiArmGripper/   Arduino sketch for 32U4 (motors + servos)
pi/
  romi_bridge.py           I2C communication with Romi 32U4
  server.py                FastAPI web server with WebSocket
  static/                  iPad-friendly touch control UI
  romi-control.service     systemd unit for auto-start
docs/setup.md              Detailed setup and troubleshooting
```

## Features

- Virtual joystick for differential drive control
- Touch sliders for three arm servos (A2, A3, A4)
- Preset positions: Home, Reach, Open Grip, Close Grip
- Real-time status: battery voltage, encoders, buttons
- Motor watchdog (auto-stop after 500 ms without commands)
- Emergency stop button

## References

- [Pololu Romi 32U4 User's Guide](https://www.pololu.com/docs/0J69/all)
- [Pololu RPi Slave Arduino Library](https://github.com/pololu/pololu-rpi-slave-arduino-library)
- [Romi Task Document](https://github.com/user-attachments/files/29475948/Romi.Task.docx)
