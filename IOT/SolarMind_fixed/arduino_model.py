"""Small educational circuit model. Inputs and outputs are simulated."""
import time


class ArduinoMonitor:
    def __init__(self, mode=0):
        if mode not in (0, 1, 2):
            raise ValueError("arduino_mode must be 0, 1 or 2")
        self.mode = mode
        self.enabled = self.led = False
        self.last_blink = time.monotonic()

    def sample(self, irradiance, now):
        # Approximate the panel as a light-dependent voltage across 1k + 100 ohms.
        light = min(1, max(0, irradiance / 800))
        panel = 5 * light
        def adc(volts):
            return min(1023, max(0, round(volts * 1023 / 5)))

        def electrical(volts, amps):
            voltage = adc(volts / 2) * 5 / 1023 * 2
            current = adc(amps * 100) * 5 / 1023 / 100
            return voltage, current * 1000, voltage * current

        v, ma, power = electrical(panel, panel / 1100)
        raw = round(light * 1023)
        if self.mode == 0:
            if raw <= 300 or power <= 0.005:
                self.enabled = True
            elif raw >= 500 and power >= 0.015:
                self.enabled = False
        elif self.mode == 1:
            if raw >= 650 and power >= 0.015:
                self.enabled = True
            elif raw <= 500 or power <= 0.005:
                self.enabled = False
        else:
            self.enabled = True
        if not self.enabled:
            self.led = False
            self.last_blink = now
        elif now - self.last_blink >= 0.5:
            self.led = not self.led
            self.last_blink = now

        # 9 V source, 1k monitoring branch and optional LED branch (2 V drop).
        bv, bma, bp = electrical(9, 9 / 1100 + (7 / 1100 if self.led else 0))
        reason = "Normal solar conditions"
        if self.mode == 2:
            reason = "Manual blink test"
        elif self.mode == 1:
            reason = "Daytime load mode"
        elif self.enabled:
            triggers = []
            if raw <= 300:
                triggers.append("darkness")
            if power <= 0.005:
                triggers.append("low solar power")
            reason = " and ".join(triggers) or "Waiting for both inputs to recover"
        return {"Mode": self.mode, "Solar voltage (V)": round(v, 2),
                "Solar current (mA)": round(ma, 2), "Solar power (W)": round(power, 4),
                "Battery voltage (V)": round(bv, 2), "Discharge current (mA)": round(bma, 2),
                "Battery output (W)": round(bp, 4), "Light ADC": raw,
                "Light voltage (V)": round(raw*5/1023, 2), "Relative light (%)": round(raw*100/1023, 1),
                "Light condition": "Dark" if raw <= 300 else "Bright" if raw >= 650 else "Moderate",
                "Load enabled": self.enabled, "LED": "On" if self.led else "Off",
                "D8": "HIGH" if self.led else "LOW", "Reason": reason}
