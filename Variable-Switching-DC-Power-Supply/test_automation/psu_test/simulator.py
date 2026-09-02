"""
Simulated bench — the reason this harness can be run and reviewed today.

None of the code in the design document can be executed without four pieces
of lab equipment and a built board, which means none of it has ever been
run and its bugs (raw-byte plotting, a telemetry parser that matches no
real firmware output, a 45 V command to a 30 V supply) were never going to
surface. This module supplies a physically plausible DUT behind the same
SCPI/serial interfaces, so:

  * every script runs end-to-end with `--simulate`;
  * the analysis maths is exercised by CI with no hardware;
  * when real instruments arrive, only the config file changes.

The buck model is deliberately simple — a droop term, a loss model and a
second-order step response. It is a harness exerciser, not a converter
model. `simulation/buck_powerstage.cir` is the tool for circuit questions.
"""

from __future__ import annotations

import math
import re
import random
import time
from dataclasses import dataclass, field

import numpy as np

from .session import register_simulated


# ── device model ──────────────────────────────────────────────────────
@dataclass
class BuckModel:
    """Behavioural model of the DUT plus the bench around it."""

    v_setpoint: float = 12.0
    i_limit: float = 5.0
    ovp_threshold: float = 32.0
    v_min: float = 1.25
    v_max: float = 30.0

    # Bench state
    bus_voltage: float = 0.0
    bus_current_limit: float = 0.0
    bus_output_on: bool = False
    load_current_cmd: float = 0.0
    load_input_on: bool = False
    load_mode: str = "CURRENT"

    # Non-idealities
    droop_ohms: float = 0.004      # 4 mOhm output impedance -> 20 mV at 5 A
    offset_error: float = -0.012   # sense-divider calibration error, volts
    noise_v: float = 0.0008
    ripple_vpp: float = 0.0226     # matches the repo's SPICE figure

    # Faults
    fault: str | None = None
    fault_time: float | None = None
    seed: int = 12345

    _rng: random.Random = field(default=None, init=False, repr=False)

    def __post_init__(self):
        self._rng = random.Random(self.seed)

    # ── behaviour ─────────────────────────────────────────────────────
    def load_current(self) -> float:
        return self.load_current_cmd if self.load_input_on else 0.0

    def v_out(self) -> float:
        """Regulated output including droop, offset, CC foldback and faults."""
        if self.fault or not self.bus_output_on:
            return 0.0
        if self.bus_voltage < self.v_setpoint + 1.5:   # dropout / UVLO region
            return max(0.0, self.bus_voltage - 1.5)

        i = self.load_current()
        if i > self.i_limit:                            # CC foldback
            return max(0.0, self.v_setpoint * (self.i_limit / i) * 0.9)

        v = self.v_setpoint + self.offset_error - i * self.droop_ohms
        return v + self._rng.gauss(0, self.noise_v)

    def efficiency(self) -> float:
        """Fraction, peaking around 3 A and falling at both ends."""
        i = self.load_current()
        if i <= 0.01:
            return 0.0
        p_out = self.v_out() * i
        if p_out <= 0:
            return 0.0
        p_fixed = 0.55                                  # gate drive, control, LED
        p_cond = 0.075 * i * i                          # I^2 R
        p_sw = 0.30 * (self.bus_voltage / 45.0)         # switching, Vin scaled
        p_in = p_out + p_fixed + p_cond + p_sw
        return p_out / p_in

    def i_bus(self) -> float:
        """Input current drawn from the bench supply, respecting its limit."""
        if not self.bus_output_on or self.bus_voltage <= 0:
            return 0.0
        eta = self.efficiency()
        p_out = self.v_out() * self.load_current()
        p_in = (p_out / eta) if eta > 0 else 0.55
        i = p_in / self.bus_voltage
        return min(i, self.bus_current_limit) if self.bus_current_limit else i

    def duty(self) -> float:
        if self.bus_voltage <= 0 or self.fault:
            return 0.0
        return min(100.0, self.v_out() / self.bus_voltage * 100.0)

    def temperature(self) -> float:
        i = self.load_current()
        return 25.0 + 3.2 * i + self._rng.gauss(0, 0.15)

    def mode(self) -> str:
        return "CC" if self.load_current() > self.i_limit else "CV"

    # ── commands ──────────────────────────────────────────────────────
    def set_output_voltage(self, volts: float) -> None:
        """Mirrors firmware behaviour: clamp to envelope, then OVP check."""
        if volts > self.ovp_threshold:
            self.trip("OVER VOLTAGE")
            return
        self.v_setpoint = max(self.v_min, min(self.v_max, volts))

    def trip(self, reason: str) -> None:
        self.fault = reason
        self.fault_time = time.time()

    def clear_fault(self) -> None:
        self.fault = None
        self.fault_time = None

    def check_overcurrent(self) -> None:
        if self.load_current() > self.i_limit + 0.5:
            self.trip("OVER CURRENT")


# ── SCPI transport ────────────────────────────────────────────────────
class SimResource:
    """Base fake VISA resource. Subclasses implement _handle()."""

    def __init__(self, model: BuckModel, idn: str):
        self.model = model
        self._idn = idn
        self.log: list[str] = []
        self.closed = False

    def write(self, cmd: str) -> None:
        self.log.append(cmd)
        self._handle(cmd, querying=False)

    def query(self, cmd: str) -> str:
        self.log.append(cmd)
        resp = self._handle(cmd, querying=True)
        if resp is None:
            raise RuntimeError(f"Simulated instrument has no answer for {cmd!r}")
        return str(resp)

    def query_binary_values(self, cmd: str, datatype: str = "B"):
        raise RuntimeError(f"{type(self).__name__} has no binary data")

    def close(self) -> None:
        self.closed = True

    # helpers
    @staticmethod
    def _arg(cmd: str) -> str:
        return cmd.split(" ", 1)[1].strip() if " " in cmd else ""

    def _common(self, cmd: str, querying: bool):
        up = cmd.upper()
        if up.startswith("*IDN?"):
            return self._idn
        if up.startswith("*OPC?"):
            return "1"
        if up.startswith("*RST"):
            self._reset()
            return None
        if up.startswith("*CLS"):
            return None
        return NotImplemented

    def _reset(self) -> None:
        pass

    def _handle(self, cmd: str, querying: bool):
        raise NotImplementedError


class SimPSU(SimResource):
    def __init__(self, model):
        super().__init__(model, "Keysight Technologies,E3634A,SIM0001,1.7")
        self.programmed_v = 0.0
        self.programmed_i = 0.0

    def _reset(self):
        self.model.bus_output_on = False
        self.model.bus_voltage = 0.0
        self.programmed_v = self.programmed_i = 0.0

    def _handle(self, cmd, querying):
        base = self._common(cmd, querying)
        if base is not NotImplemented:
            return base
        up = cmd.upper()
        if ":VOLT" in up and "MEAS" not in up:
            if up.rstrip().endswith("?"):
                return f"{self.programmed_v:.4f}"
            self.programmed_v = float(self._arg(cmd))
            self.model.bus_voltage = self.programmed_v
            return None
        if ":CURR" in up and "MEAS" not in up:
            if up.rstrip().endswith("?"):
                return f"{self.programmed_i:.4f}"
            self.programmed_i = float(self._arg(cmd))
            self.model.bus_current_limit = self.programmed_i
            return None
        if up.startswith(":OUTP"):
            self.model.bus_output_on = "ON" in up
            return None
        if "MEAS" in up and "VOLT" in up:
            return f"{self.model.bus_voltage if self.model.bus_output_on else 0.0:.4f}"
        if "MEAS" in up and "CURR" in up:
            return f"{self.model.i_bus():.5f}"
        return None


class SimLoad(SimResource):
    def __init__(self, model):
        super().__init__(model, "KEYSIGHT,N3300A,SIM0002,1.0")

    def _reset(self):
        self.model.load_input_on = False
        self.model.load_current_cmd = 0.0

    def _handle(self, cmd, querying):
        base = self._common(cmd, querying)
        if base is not NotImplemented:
            return base
        up = cmd.upper()
        if ":FUNC" in up:
            self.model.load_mode = self._arg(cmd).upper()
            return None
        if "TRAN" in up:
            return None
        if ":CURR" in up and "MEAS" not in up and "SLEW" not in up:
            if up.rstrip().endswith("?"):
                return f"{self.model.load_current_cmd:.4f}"
            self.model.load_current_cmd = float(self._arg(cmd))
            self.model.check_overcurrent()
            return None
        if "SLEW" in up:
            return None
        if up.startswith(":INP"):
            self.model.load_input_on = "ON" in up
            self.model.check_overcurrent()
            return None
        if "MEAS" in up and "VOLT" in up:
            return f"{self.model.v_out():.5f}"
        if "MEAS" in up and "CURR" in up:
            return f"{self.model.load_current():.5f}"
        return None


class SimDMM(SimResource):
    def __init__(self, model):
        super().__init__(model, "Keysight Technologies,34461A,SIM0003,A.02.14")

    def _handle(self, cmd, querying):
        base = self._common(cmd, querying)
        if base is not NotImplemented:
            return base
        up = cmd.upper()
        if up.startswith("CONF") or "NPLC" in up:
            return None
        if up.startswith("READ?") or up.startswith("MEAS"):
            return f"{self.model.v_out():.6f}"
        return None


class SimScope(SimResource):
    """
    Fake scope that synthesises a second-order load-step response and a
    switching-ripple trace, then serves them through the real preamble
    protocol so the scaling path in scope.get_waveform_scaled is exercised.
    """

    POINTS = 1200
    DIVS = 12

    def __init__(self, model):
        super().__init__(model, "RIGOL TECHNOLOGIES,DS1054Z,SIM0004,00.04.04")
        self.timebase = 100e-6
        self.channel_scale = {1: 0.5, 2: 2.0}
        self.channel_offset = {1: 0.0, 2: 0.0}
        self.coupling = {1: "DC", 2: "DC"}
        self.source = 1
        self.armed = False
        self.stopped = True
        self.armed_at = 0.0
        self.trigger_delay_s = 0.15   # emulates arm-to-capture latency
        self.mode = "transient"     # "transient" | "ripple" | "protection"

    def _reset(self):
        self.__init__(self.model)

    # waveform generation ------------------------------------------------
    def _time_axis(self):
        span = self.timebase * self.DIVS
        dt = span / self.POINTS
        t = (np.arange(self.POINTS) - self.POINTS / 4) * dt   # trigger at 25%
        return t, dt

    def _volts(self, ch: int) -> np.ndarray:
        t, _ = self._time_axis()
        m = self.model
        if self.mode == "protection":
            v = np.where(t < 0, m.v_setpoint, 0.0).astype(float)
            tau = 4e-6
            fall = t >= 0
            v[fall] = m.v_setpoint * np.exp(-t[fall] / tau)
            return v + np.random.default_rng(7).normal(0, 0.01, t.size)
        if self.mode == "ripple":
            f_sw = 200e3
            return (m.ripple_vpp / 2) * np.sin(2 * math.pi * f_sw * t) \
                + np.random.default_rng(3).normal(0, m.ripple_vpp / 40, t.size)

        # transient: 0 -> I_step at t = 0, second-order recovery
        v_final = m.v_setpoint + m.offset_error - m.load_current_cmd * m.droop_ohms
        v0 = m.v_setpoint + m.offset_error
        wn, zeta = 2 * math.pi * 3.5e3, 0.55
        wd = wn * math.sqrt(1 - zeta ** 2)
        dip = 0.32                                  # volts of undershoot
        v = np.full(t.size, v0, dtype=float)
        post = t >= 0
        tp = t[post]
        env = np.exp(-zeta * wn * tp)
        v[post] = v_final - dip * env * np.cos(wd * tp)
        rng = np.random.default_rng(11)
        return v + rng.normal(0, 0.004, t.size)

    def _encode(self, volts: np.ndarray, ch: int):
        """Volts -> 8-bit codes using the same relation the driver inverts."""
        y_inc = self.channel_scale[ch] / 25.0        # 25 codes per division
        y_ref = 127.0
        y_orig = -self.channel_offset[ch] / y_inc
        codes = np.clip(np.round(volts / y_inc + y_orig + y_ref), 0, 255)
        return codes.astype(int), y_inc, y_orig, y_ref

    # SCPI ---------------------------------------------------------------
    def _handle(self, cmd, querying):
        base = self._common(cmd, querying)
        if base is not NotImplemented:
            return base
        up = cmd.upper()

        if up.startswith(":TIM") and "SCAL" in up:
            if up.rstrip().endswith("?"):
                return f"{self.timebase:.6e}"
            self.timebase = float(self._arg(cmd))
            return None
        if up.startswith(":TIM") and "OFFS" in up:
            return None
        if up.startswith(":CHAN"):
            m = re.match(r":CHAN(?:NEL)?(\d)", up)
            if m is None:
                return None
            ch = int(m.group(1))
            if "SCAL" in up:
                if up.rstrip().endswith("?"):
                    return f"{self.channel_scale[ch]}"
                self.channel_scale[ch] = float(self._arg(cmd))
            elif "OFFS" in up:
                if up.rstrip().endswith("?"):
                    return f"{self.channel_offset[ch]}"
                self.channel_offset[ch] = float(self._arg(cmd))
            elif "COUP" in up:
                if up.rstrip().endswith("?"):
                    return self.coupling[ch]
                self.coupling[ch] = self._arg(cmd).upper()
            elif "BWL" in up:
                return None
            return None
        if up.startswith(":TRIG"):
            if "STAT" in up:
                if (self.armed and not self.stopped
                        and time.monotonic() - self.armed_at
                        >= self.trigger_delay_s):
                    self.stopped = True     # acquisition complete
                return "STOP" if self.stopped else "WAIT"
            return None
        if up.startswith(":SING"):
            self.armed, self.stopped = True, False
            self.armed_at = time.monotonic()
            return None
        if up.startswith(":RUN"):
            self.stopped = False
            return None
        if up.startswith(":STOP"):
            self.stopped = True
            return None
        if up.startswith(":AUT"):
            return None
        if up.startswith(":WAV"):
            if "SOUR" in up and not up.rstrip().endswith("?"):
                self.source = int(self._arg(cmd).upper().replace("CHANNEL", ""))
                return None
            if "PRE" in up:
                _, dt = self._time_axis()
                volts = self._volts(self.source)
                _, y_inc, y_orig, y_ref = self._encode(volts, self.source)
                # x_reference alone carries the trigger position; adding a
                # non-zero x_origin here would shift the driver's time axis
                # relative to the generated waveform.
                x_ref = self.POINTS / 4
                x_orig = 0.0
                return (f"0,0,{self.POINTS},1,{dt:.9e},{x_orig:.9e},{x_ref:.1f},"
                        f"{y_inc:.9e},{y_orig:.6f},{y_ref:.1f}")
            return None
        if up.startswith(":MEAS"):
            volts = self._volts(self.source)
            if "VPP" in up:
                return f"{float(volts.max() - volts.min()):.6f}"
            if "FREQ" in up:
                return "2.000000E+05"
        return None

    def query_binary_values(self, cmd: str, datatype: str = "B"):
        self.log.append(cmd)
        if "DATA" not in cmd.upper():
            raise RuntimeError(f"Unexpected binary query {cmd!r}")
        # Note: preamble is regenerated per call from the same deterministic
        # generator, so codes and scaling stay consistent.
        codes, *_ = self._encode(self._volts(self.source), self.source)
        return codes.tolist()


# ── serial transport ──────────────────────────────────────────────────
class SimSerial:
    """
    Fake STM32 UART.

    `csv_format=False` reproduces the line the firmware in this repo actually
    prints, which is what makes the format-mismatch problem reproducible in
    CI. `csv_format=True` reproduces the documented format produced by
    firmware_patch/telemetry.c.
    """

    def __init__(self, model: BuckModel, *, csv_format: bool = False,
                 period_s: float = 0.1, accepts_commands: bool = True):
        self.model = model
        self.csv_format = csv_format
        self.period_s = period_s
        self.accepts_commands = accepts_commands
        self._next = 0.0
        self._pending: list[bytes] = []
        self._last_fault_emitted: float | None = None
        self.closed = False

    def _line(self) -> bytes:
        m = self.model
        if self.csv_format:
            status = "FAULT" if m.fault else "OK"
            return (f"{m.v_setpoint:.3f},{m.v_out():.3f},{m.load_current():.3f},"
                    f"{m.duty():.2f},{m.temperature():.1f},{status}\r\n"
                    ).encode()
        return (f"Vset={m.v_setpoint:.2f} Vout={m.v_out():.2f} "
                f"Iout={m.load_current():.2f} T={m.temperature():.1f}C "
                f"[{m.mode()}]\r\n").encode()

    def readline(self) -> bytes:
        if self._pending:
            return self._pending.pop(0)
        if (self.model.fault_time is not None
                and self.model.fault_time != self._last_fault_emitted):
            self._last_fault_emitted = self.model.fault_time
            return f"FAULT: {self.model.fault}\r\n".encode()
        now = time.monotonic()
        wait = self._next - now
        if wait > 0:
            time.sleep(min(wait, 0.2))
        self._next = time.monotonic() + self.period_s
        return self._line()

    def write(self, data: bytes) -> int:
        if not self.accepts_commands:
            return len(data)                      # stock firmware: discarded
        cmd = data.decode("ascii", errors="replace").strip()
        parts = cmd.split()
        if len(parts) == 2 and parts[0].upper() == "SETV":
            self.model.set_output_voltage(float(parts[1]))
        elif len(parts) == 2 and parts[0].upper() == "SETI":
            self.model.i_limit = float(parts[1])
        elif parts and parts[0].upper() == "CLEARFAULT":
            self.model.clear_fault()
        return len(data)

    def close(self) -> None:
        self.closed = True


# ── bench assembly ────────────────────────────────────────────────────
@dataclass
class SimulatedBench:
    model: BuckModel
    psu: SimPSU
    load: SimLoad
    dmm: SimDMM
    scope: SimScope
    serial: SimSerial


def build_bench(config, *, csv_telemetry: bool = True,
                accepts_commands: bool = True,
                model: BuckModel | None = None) -> SimulatedBench:
    """
    Instantiate a simulated bench and register it against the config's
    resource strings, so `simulate=True` code paths resolve to it.

    csv_telemetry=False reproduces the current firmware's output format —
    use it to prove the harness degrades honestly rather than silently.
    """
    m = model or BuckModel(v_setpoint=config.limits.v_nominal,
                           i_limit=config.limits.i_max)
    bench = SimulatedBench(
        model=m,
        psu=SimPSU(m),
        load=SimLoad(m),
        dmm=SimDMM(m),
        scope=SimScope(m),
        serial=SimSerial(m, csv_format=csv_telemetry,
                         accepts_commands=accepts_commands),
    )
    register_simulated(config.psu, bench.psu)
    register_simulated(config.load, bench.load)
    register_simulated(config.dmm, bench.dmm)
    register_simulated(config.scope, bench.scope)
    if config.stm32_port:
        register_simulated(config.stm32_port, bench.serial)
    return bench
