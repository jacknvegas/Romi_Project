# Romi iPad Control — Setup Guide

## Hardware Overview

| Component | Role |
|-----------|------|
| Romi 32U4 | Motor control, servo PWM, sensors (I2C slave @ address 20) |
| Raspberry Pi 5 | WiFi, Python web server, I2C master |
| iPad | Browser-based touch control panel |
| Arm servos | Pins 20/A2 (base), 21/A3 (shoulder), 22/A4 (gripper) |

## 1. Arduino Firmware (Romi 32U4)

### Install libraries

In Arduino IDE Library Manager, install:

- **PololuRPiSlave**
- **Romi32U4**

### Modify Servo library for Timer3

The standard Arduino `Servo` library uses Timer1, which conflicts with Romi motor drivers. Change it to Timer3:

1. Open `libraries/Servo/src/avr/ServoTimers.h` in your Arduino installation.
2. Find the `__AVR_ATmega32U4__` section.
3. Change `_useTimer1` to `_useTimer3` and `_timer1` to `_timer3`.
4. Save the file.

See [Pololu servo documentation](https://www.pololu.com/docs/0J69/3.9.1) for details.

### Upload firmware

1. Connect the Romi 32U4 via USB to your MacBook Air.
2. In Arduino IDE, open `firmware/RomiArmGripper/RomiArmGripper.ino`.
3. Select board **Pololu A-Star 32U4** (or Arduino Leonardo).
4. Upload the sketch.

## 2. Raspberry Pi Setup

### Enable I2C

```bash
sudo raspi-config
# Interface Options → I2C → Enable
```

Optional: increase I2C speed to 400 kHz in `/boot/firmware/config.txt`:

```
dtparam=i2c_arm_baudrate=400000
```

### Verify I2C connection

With the Pi mounted on the Romi and firmware uploaded:

```bash
sudo i2cdetect -y 1
```

You should see device `20` (Romi 32U4) and `6b` (onboard IMU).

### Install Python dependencies

```bash
cd ~/Romi_Project/pi
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

On Raspberry Pi OS you may also need:

```bash
sudo apt install python3-smbus i2c-tools
```

### Run the control server

```bash
cd ~/Romi_Project/pi
source venv/bin/activate
python3 server.py
```

The server listens on port **8000**.

### Auto-start on boot (optional)

```bash
sudo cp romi-control.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable romi-control
sudo systemctl start romi-control
```

## 3. iPad Control

1. Connect the Raspberry Pi and iPad to the same WiFi network.
2. Find the Pi's IP address (`hostname -I` on the Pi).
3. On the iPad, open Safari and go to `http://<pi-ip>:8000`.
4. For a home-screen shortcut: Share → Add to Home Screen.

### Controls

- **Joystick** — drive forward/back and turn
- **Arm sliders** — set servo angles for base (A2), shoulder (A3), gripper (A4)
- **Presets** — Home, Reach, Open Grip, Close Grip
- **Stop / E-Stop** — halt motors immediately

The server stops motors automatically if no drive commands arrive for 500 ms.

## 4. I2C Protocol Extension

The firmware extends the Pololu buffer with three servo bytes at offsets 43–45:

| Offset | Field | Type | Range |
|--------|-------|------|-------|
| 43 | servoA2 | uint8 | 0–180° |
| 44 | servoA3 | uint8 | 0–180° |
| 45 | servoA4 | uint8 | 0–180° |

Python access via `romi_bridge.py`:

```python
from romi_bridge import RomiBridge

romi = RomiBridge()
romi.set_motors(200, 200)
romi.set_servos(90, 45, 120)
status = romi.read_status()
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| No device at I2C address 20 | Re-upload firmware; check Pi is seated on Romi HAT connector |
| Servos jitter or motors stop | Confirm Servo library uses Timer3 |
| iPad cannot connect | Verify same WiFi network; check firewall allows port 8000 |
| Motors run after disconnect | Watchdog stops motors after 500 ms; E-Stop also available |
