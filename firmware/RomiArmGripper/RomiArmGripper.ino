/*
 * RomiArmGripper - I2C slave firmware for Romi 32U4 with arm/gripper servos.
 *
 * Extends the Pololu RomiRPiSlaveDemo to drive three arm servos on:
 *   Pin 20 / A2 - base rotation
 *   Pin 21 / A3 - shoulder
 *   Pin 22 / A4 - gripper
 *
 * Prerequisites:
 *   - PololuRPiSlave library (Arduino Library Manager)
 *   - Romi32U4 library (Arduino Library Manager)
 *   - Modify Arduino Servo library to use Timer3 instead of Timer1
 *     (see docs/setup.md) so servos do not conflict with motor control.
 *
 * Upload this sketch to the Romi 32U4 with Arduino IDE.
 */

#include <Servo.h>
#include <Romi32U4.h>
#include <PololuRPiSlave.h>

// I2C buffer layout shared with pi/romi_bridge.py — keep offsets in sync.
struct Data
{
  bool yellow, green, red;
  bool buttonA, buttonB, buttonC;

  int16_t leftMotor, rightMotor;
  uint16_t batteryMillivolts;
  uint16_t analog[6];

  bool playNotes;
  char notes[14];

  int16_t leftEncoder, rightEncoder;

  // Arm servos: angles 0-180 degrees
  uint8_t servoA2;
  uint8_t servoA3;
  uint8_t servoA4;
};

PololuRPiSlave<struct Data, 5> slave;
PololuBuzzer buzzer;
Romi32U4Motors motors;
Romi32U4ButtonA buttonA;
Romi32U4ButtonB buttonB;
Romi32U4ButtonC buttonC;
Romi32U4Encoders encoders;

Servo servoBase;    // Pin 20 / A2
Servo servoShoulder; // Pin 21 / A3
Servo servoGripper;  // Pin 22 / A4

static const uint8_t PIN_SERVO_A2 = 20;
static const uint8_t PIN_SERVO_A3 = 21;
static const uint8_t PIN_SERVO_A4 = 22;

static const uint8_t DEFAULT_SERVO_A2 = 90;
static const uint8_t DEFAULT_SERVO_A3 = 90;
static const uint8_t DEFAULT_SERVO_A4 = 45;

static uint8_t clampAngle(uint8_t angle)
{
  return angle > 180 ? 180 : angle;
}

void setup()
{
  slave.init(20);

  servoBase.attach(PIN_SERVO_A2);
  servoShoulder.attach(PIN_SERVO_A3);
  servoGripper.attach(PIN_SERVO_A4);

  servoBase.write(DEFAULT_SERVO_A2);
  servoShoulder.write(DEFAULT_SERVO_A3);
  servoGripper.write(DEFAULT_SERVO_A4);

  slave.buffer.servoA2 = DEFAULT_SERVO_A2;
  slave.buffer.servoA3 = DEFAULT_SERVO_A3;
  slave.buffer.servoA4 = DEFAULT_SERVO_A4;

  buzzer.play("v10>>g16>>>c16");
}

void loop()
{
  slave.updateBuffer();

  slave.buffer.buttonA = buttonA.isPressed();
  slave.buffer.buttonB = buttonB.isPressed();
  slave.buffer.buttonC = buttonC.isPressed();
  slave.buffer.batteryMillivolts = readBatteryMillivolts();

  for (uint8_t i = 0; i < 6; i++)
  {
    slave.buffer.analog[i] = analogRead(i);
  }

  ledYellow(slave.buffer.yellow);
  ledGreen(slave.buffer.green);
  ledRed(slave.buffer.red);
  motors.setSpeeds(slave.buffer.leftMotor, slave.buffer.rightMotor);

  servoBase.write(clampAngle(slave.buffer.servoA2));
  servoShoulder.write(clampAngle(slave.buffer.servoA3));
  servoGripper.write(clampAngle(slave.buffer.servoA4));

  static bool startedPlaying = false;
  if (slave.buffer.playNotes && !startedPlaying)
  {
    buzzer.play(slave.buffer.notes);
    startedPlaying = true;
  }
  else if (startedPlaying && !buzzer.isPlaying())
  {
    slave.buffer.playNotes = false;
    startedPlaying = false;
  }

  slave.buffer.leftEncoder = encoders.getCountsLeft();
  slave.buffer.rightEncoder = encoders.getCountsRight();

  slave.finalizeWrites();
}
