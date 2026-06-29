(() => {
  "use strict";

  const MAX_MOTOR = 400;
  const WS_URL = `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`;
  const SERVO_DEBOUNCE_MS = 80;
  const DRIVE_SEND_MS = 50;

  let ws = null;
  let reconnectTimer = null;
  let servoTimer = null;
  let driveTimer = null;
  let joystickActive = false;

  const els = {
    connection: document.getElementById("connection-status"),
    motorLeft: document.getElementById("motor-left"),
    motorRight: document.getElementById("motor-right"),
    battery: document.getElementById("battery"),
    encLeft: document.getElementById("enc-left"),
    encRight: document.getElementById("enc-right"),
    buttons: document.getElementById("buttons"),
    joystick: document.getElementById("joystick"),
    knob: document.getElementById("joystick-knob"),
    servoA2: document.getElementById("servo-a2"),
    servoA3: document.getElementById("servo-a3"),
    servoA4: document.getElementById("servo-a4"),
    servoA2Val: document.getElementById("servo-a2-val"),
    servoA3Val: document.getElementById("servo-a3-val"),
    servoA4Val: document.getElementById("servo-a4-val"),
    stopBtn: document.getElementById("stop-btn"),
    estopBtn: document.getElementById("estop-btn"),
  };

  function setConnection(connected) {
    els.connection.textContent = connected ? "Connected" : "Disconnected";
    els.connection.classList.toggle("connected", connected);
    els.connection.classList.toggle("disconnected", !connected);
  }

  function send(payload) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(payload));
    }
  }

  function connect() {
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    ws = new WebSocket(WS_URL);

    ws.onopen = () => {
      setConnection(true);
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
    };

    ws.onclose = () => {
      setConnection(false);
      reconnectTimer = setTimeout(connect, 1500);
    };

    ws.onerror = () => {
      ws.close();
    };

    ws.onmessage = (event) => {
      let data;
      try {
        data = JSON.parse(event.data);
      } catch {
        return;
      }

      if (data.type === "status") {
        if (data.error) return;
        els.battery.textContent = `${data.battery_millivolts} mV`;
        els.encLeft.textContent = data.encoders[0];
        els.encRight.textContent = data.encoders[1];
        const [a, b, c] = data.buttons;
        els.buttons.textContent = `A:${a ? "●" : "○"} B:${b ? "●" : "○"} C:${c ? "●" : "○"}`;
        if (data.servos && !servoTimer) {
          updateServoSliders(data.servos[0], data.servos[1], data.servos[2], false);
        }
        if (data.motors) {
          els.motorLeft.textContent = data.motors[0];
          els.motorRight.textContent = data.motors[1];
        }
      }

      if (data.servos) {
        updateServoSliders(data.servos[0], data.servos[1], data.servos[2], false);
      }
    };
  }

  function updateServoSliders(a2, a3, a4, sendUpdate) {
    els.servoA2.value = a2;
    els.servoA3.value = a3;
    els.servoA4.value = a4;
    els.servoA2Val.textContent = `${a2}°`;
    els.servoA3Val.textContent = `${a3}°`;
    els.servoA4Val.textContent = `${a4}°`;

    if (sendUpdate) {
      clearTimeout(servoTimer);
      servoTimer = setTimeout(() => {
        send({
          type: "servos",
          a2: Number(els.servoA2.value),
          a3: Number(els.servoA3.value),
          a4: Number(els.servoA4.value),
        });
        servoTimer = null;
      }, SERVO_DEBOUNCE_MS);
    }
  }

  function sendDrive(left, right) {
    els.motorLeft.textContent = left;
    els.motorRight.textContent = right;
    clearTimeout(driveTimer);
    driveTimer = setTimeout(() => {
      send({ type: "drive", left, right });
    }, DRIVE_SEND_MS);
  }

  function initJoystick() {
    const pad = els.joystick;
    const knob = els.knob;
    const radius = pad.clientWidth / 2;
    const knobRadius = knob.clientWidth / 2;
    const maxDistance = radius - knobRadius - 4;

    function handleMove(clientX, clientY) {
      const rect = pad.getBoundingClientRect();
      const centerX = rect.left + radius;
      const centerY = rect.top + radius;
      let dx = clientX - centerX;
      let dy = clientY - centerY;
      const dist = Math.hypot(dx, dy);

      if (dist > maxDistance) {
        dx = (dx / dist) * maxDistance;
        dy = (dy / dist) * maxDistance;
      }

      knob.style.transform = `translate(calc(-50% + ${dx}px), calc(-50% + ${dy}px))`;

      const forward = -dy / maxDistance;
      const turn = dx / maxDistance;
      const left = Math.round((forward + turn) * MAX_MOTOR);
      const right = Math.round((forward - turn) * MAX_MOTOR);
      sendDrive(left, right);
    }

    function resetKnob() {
      knob.style.transform = "translate(-50%, -50%)";
      sendDrive(0, 0);
    }

    function onStart(e) {
      e.preventDefault();
      joystickActive = true;
      const point = e.touches ? e.touches[0] : e;
      handleMove(point.clientX, point.clientY);
    }

    function onMove(e) {
      if (!joystickActive) return;
      e.preventDefault();
      const point = e.touches ? e.touches[0] : e;
      handleMove(point.clientX, point.clientY);
    }

    function onEnd() {
      joystickActive = false;
      resetKnob();
    }

    pad.addEventListener("mousedown", onStart);
    pad.addEventListener("touchstart", onStart, { passive: false });
    window.addEventListener("mousemove", onMove);
    window.addEventListener("touchmove", onMove, { passive: false });
    window.addEventListener("mouseup", onEnd);
    window.addEventListener("touchend", onEnd);
    window.addEventListener("touchcancel", onEnd);
  }

  [els.servoA2, els.servoA3, els.servoA4].forEach((slider) => {
    slider.addEventListener("input", () => {
      updateServoSliders(
        Number(els.servoA2.value),
        Number(els.servoA3.value),
        Number(els.servoA4.value),
        true
      );
    });
  });

  document.querySelectorAll(".preset-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      send({ type: "preset", name: btn.dataset.preset });
    });
  });

  els.stopBtn.addEventListener("click", () => send({ type: "stop" }));
  els.estopBtn.addEventListener("click", () => send({ type: "estop" }));

  initJoystick();
  connect();
})();
