"""The guided hardware test: tells the person what to do, measures, grades, writes a report.

Steps run in this order: find the headband, read its firmware, stream every sensor, time ten
connections, check sensor contact, make the 10-minute recording with markers, recover from a
power-off, stop a recording with Ctrl+C. Ctrl+C at any other moment stops the run and still
writes the report.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Collection, Generator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from mufuse.acquisition.athena import ATHENA_STREAMS
from mufuse.acquisition.muse_control import DeviceInfoError, split_device_info
from mufuse.acquisition.source import HeadbandSource
from mufuse.acquisition.supervisor import State, StreamSupervisor
from mufuse.acquisition.types import FloatArray, FoundDevice, SourceError, StreamKind
from mufuse.hwtest.background import BackgroundAcquisition
from mufuse.hwtest.bench import Bench, DeviceDetails, pick_device
from mufuse.hwtest.checks import (
    CHECK_ORDER,
    CHECKS,
    CheckResult,
    Condition,
    Pause,
    Timings,
    evaluate_connect,
    evaluate_contact,
    evaluate_interrupt,
    evaluate_markers,
    evaluate_power,
    evaluate_record,
    evaluate_streams,
    result,
    skipped,
)
from mufuse.hwtest.operator import Action, KeyReader
from mufuse.hwtest.report import Report, environment
from mufuse.recording.format import Marker, new_session_id
from mufuse.recording.reader import LoadedSession, load_session
from mufuse.recording.writer import SessionWriter

EEG_RATE = ATHENA_STREAMS[StreamKind.EEG].sampling_rate
TICK_S = 0.05
LOW_BATTERY = 30.0


class StepError(RuntimeError):
    """A step could not finish (for example, acquisition stopped with an error)."""


@dataclass(frozen=True)
class Step:
    key: str
    title: str
    checks: tuple[str, ...]
    run: Callable[[HardwareTest], list[CheckResult]]
    seconds: Callable[[Timings], float]


class HardwareTest:
    def __init__(
        self,
        bench: Bench,
        out: Path,
        *,
        timings: Timings | None = None,
        only: Collection[str] | None = None,
        practice: bool = False,
        clock: Callable[[], float] = time.time,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        unknown = set(only or ()) - set(CHECK_ORDER)
        if unknown:
            raise ValueError(
                f"Unknown check {', '.join(sorted(unknown))}. Choose from: {', '.join(CHECK_ORDER)}"
            )
        self.bench = bench
        self.op = bench.operator
        self.t = timings or Timings()
        self.out = out
        self.practice = practice
        self.selected = {"find", *(only or CHECK_ORDER)}
        self.clock = clock
        self.sleep = sleep
        self.device: FoundDevice | None = None
        self.details = DeviceDetails()
        self.run_dir = out
        self.sessions: dict[str, str] = {}

    # --- the run ----------------------------------------------------------------------------

    def run(self) -> Report:
        started = self.clock()
        run_id = new_session_id(started)
        self.run_dir = self.out / run_id
        self.run_dir.mkdir(parents=True, exist_ok=False)
        steps = [s for s in STEPS if self.selected & set(s.checks)]
        results: dict[str, CheckResult] = {}
        stop_reason = ""
        aborted = False
        try:
            self._intro(steps)
            for number, step in enumerate(steps, 1):
                title = step.title.format(record=_duration(self.t.record_s).capitalize())
                self.op.heading(number, len(steps), title, _about(step.seconds(self.t)))
                try:
                    step_results = step.run(self)
                except SourceError as exc:
                    step_results = _all_failed(step, f"Could not connect to the headband: {exc}")
                except StepError as exc:
                    step_results = _all_failed(step, str(exc))
                for r in step_results:
                    results[r.key] = r
                    self.op.show_result(r)
                if step.key == "find" and self.device is None:
                    stop_reason = "the headband was not found"
                    break
        except KeyboardInterrupt:
            aborted = True
            stop_reason = "you pressed Ctrl+C"
            self.op.say("\nStopped. Writing the report for the checks that finished.")
        not_run = f"Not run: {stop_reason}" if stop_reason else "Not run"
        ordered = [
            results.get(key) or skipped(key, not_run if key in self.selected else "Not selected")
            for key in CHECK_ORDER
        ]
        report = Report(
            run_id=run_id,
            run_dir=self.run_dir,
            started_at=started,
            finished_at=self.clock(),
            bench=self.bench.description,
            practice=self.practice,
            simulated=self.bench.simulated,
            aborted=aborted,
            stop_reason=stop_reason,
            device={
                "name": self.device.name if self.device else None,
                "firmware": self.details.firmware,
                "extra": self.details.extra,
                "preset": self.bench.preset,
            },
            environment=environment(),
            timings=self.t,
            results=ordered,
            sessions=self.sessions,
        )
        report.write()
        self._outro(report)
        return report

    def _intro(self, steps: list[Step]) -> None:
        total = sum(s.seconds(self.t) for s in steps)
        self.op.say(
            f"This guided test checks the headband connection, recording and recovery. "
            f"It has {len(steps)} steps and takes {_about(total)}. Each step explains itself "
            "first; when a highlighted ▶ direction appears, do it straight away."
        )
        if self.bench.simulated:
            self.op.say("Dry run: a simulated headband and a simulated you follow the directions.")
        if self.practice:
            self.op.say(
                "Practice run: the tests are shortened, so the report doesn't count as the "
                "acceptance record."
            )
        self.op.say("You can press Ctrl+C at any time to stop; finished checks are still saved.")

    def _outro(self, report: Report) -> None:
        self.op.say("")
        self.op.say(f"[bold]{report.summary()}.[/bold]")
        self.op.say(f"Report: {report.run_dir / 'report.md'}", wrap=False)
        if not report.simulated and not report.practice:
            self.op.say("Paste report.md into the feature 001 pull request.")

    # --- steps ------------------------------------------------------------------------------

    def step_find(self) -> list[CheckResult]:
        self.op.say(
            "Switch the headband on and put it on. Close the Muse app on your phone: the headband "
            "talks to one device at a time. Stay within 2 m of this computer for the whole test."
        )
        self.op.wait_for_enter()
        self.op.progress("Scanning for Muse headbands…")
        found = self.bench.scan(self.t.scan_s)
        criterion = "The headband shows up in a Bluetooth scan"
        if not found:
            return [
                result(
                    "find",
                    False,
                    "No Muse headband found. Check that it is on and charged and that the Muse "
                    "phone app is closed, then run the test again.",
                    criterion,
                )
            ]
        device = pick_device(found, self.bench.saved_device)
        self.bench.remember(device)
        self.device = device
        others = [d.name for d in found if d is not device]
        measured = f"Found {device.name} (signal {device.rssi} dBm)"
        if others:
            measured += f"; also nearby: {', '.join(others)}"
        details = {"name": device.name, "rssi": device.rssi, "others": others}
        return [result("find", True, measured, criterion, details)]

    def step_firmware(self) -> list[CheckResult]:
        device = self._device()
        self.op.say("Reading the headband's firmware version. Nothing to do; this takes seconds.")
        criterion = "The headband reports its firmware version, which is saved with each recording"
        try:
            info = self.bench.read_info(device, self.t.info_timeout_s)
        except DeviceInfoError as exc:
            return [
                result(
                    "firmware",
                    False,
                    f"Could not read it ({exc}). Recordings still work, without the version.",
                    criterion,
                )
            ]
        firmware, extra = split_device_info(info)
        self.details = DeviceDetails(firmware, extra)
        measured = f"Firmware {firmware}" if firmware else "The reply had no firmware version"
        if "hw" in extra:
            measured += f", hardware {extra['hw']}"
        return [result("firmware", firmware is not None, measured, criterion, dict(info))]

    def step_streams(self) -> list[CheckResult]:
        self.op.say(
            "Sit comfortably and keep still. I'll check that the EEG, motion and optical sensors "
            f"all send data for {self.t.stream_s:.0f} seconds."
        )
        self.op.wait_for_enter()
        with self._streaming() as acq:
            self._wait(self.t.settle_s, acq)
            before, t0 = acq.counts(), self.clock()
            self.op.progress(f"Measuring for {self.t.stream_s:.0f} s…")
            self._wait(self.t.stream_s, acq)
            after, t1 = acq.counts(), self.clock()
            battery = _battery(acq.latest(StreamKind.OPTICS))
        if battery is not None and battery < LOW_BATTERY:
            self.op.say(
                f"The battery is at {battery:.0f}%. Charge it before the long recording if you can."
            )
        received = {k: after[k] - before[k] for k in StreamKind}
        return [evaluate_streams(received, t1 - t0, battery)]

    def step_connect(self) -> list[CheckResult]:
        n = self.t.connect_attempts
        self.op.say(
            f"Next I'll connect and disconnect {n} times and time how long live EEG takes to "
            "appear. Keep the headband on; you don't need to do anything."
        )
        self.op.wait_for_enter()
        times: list[float | None] = []
        for attempt in range(1, n + 1):
            seconds = self._time_one_connection()
            times.append(seconds)
            shown = f"{seconds:.1f} s" if seconds is not None else "could not connect"
            self.op.progress(f"Attempt {attempt} of {n}: {shown}")
            if attempt < n:
                self.sleep(self.t.connect_pause_s)
        return [evaluate_connect(times)]

    def step_contact(self) -> list[CheckResult]:
        self.op.say(
            "This checks the per-sensor contact indicator and collects numbers for tuning it. "
            "There are four short parts. Read each direction, then hold it until I say done."
        )
        self.op.wait_for_enter()
        parts = [
            (
                Condition.REST,
                Action.REST,
                self.t.rest_s,
                "Sit still with your eyes open and your face relaxed.",
                "Done.",
            ),
            (
                Condition.BLINK,
                Action.BLINK,
                self.t.blink_s,
                "Blink firmly, about once a second.",
                "Done. You can stop blinking.",
            ),
            (
                Condition.CLENCH,
                Action.CLENCH,
                self.t.clench_s,
                "Clench your jaw hard and hold it.",
                "Done. Relax your jaw.",
            ),
            (
                Condition.LIFT_TP9,
                Action.LIFT_TP9,
                self.t.lift_s,
                "Slide a finger under the band behind your LEFT ear so that sensor lifts off "
                "your skin, and hold it there.",
                "Done. Let the sensor rest against your skin again.",
            ),
        ]
        samples: dict[Condition, FloatArray] = {}
        with self._streaming() as acq:
            self._wait(self.t.settle_s, acq)
            for condition, action, seconds, direction, done in parts:
                self.op.instruct(direction)
                self.op.countdown(self.t.countdown_s, "Starting in")
                self.op.act(action)
                start = self.clock()
                self.op.progress(f"Hold it for {seconds:.0f} s…")
                self._wait(seconds, acq)
                end = self.clock()
                self.op.act(Action.RELAX)
                self.op.say(done)
                self._wait(self.t.drain_s, acq)
                samples[condition] = acq.eeg_between(start, end)[1]
                self._wait(self.t.recover_s, acq)
        return [evaluate_contact(samples, EEG_RATE, self.t.contact_window_s)]

    def step_record(self) -> list[CheckResult]:
        n = len(self.t.marker_at_s)
        self.op.say(
            f"Now a {_duration(self.t.record_s)} recording. Stay within 2 m of the computer and "
            "keep the headband on; you can read or relax. "
            f"I'll ask you to press SPACE {n} times. Press it as soon as you see the prompt."
        )
        self.op.wait_for_enter()
        captured: list[float] = []
        label = f"{_duration(self.t.record_s)} recording"
        notes = f"hardware test: {label}"
        with self._streaming(notes) as acq, self.op.capture_keys() as read_key:
            start = self.clock()
            end = start + self.t.record_s
            due = [start + s for s in self.t.marker_at_s]
            next_progress = start + self.t.progress_every_s
            last_counts, last_t = acq.counts(), start
            while (now := self.clock()) < end:
                if due and now >= due[0]:
                    due.pop(0)
                    number = n - len(due)
                    self.op.instruct(f"Press SPACE now (marker {number} of {n}).")
                    self.op.act(Action.PRESS_SPACE)
                    pressed = self._wait_for_key(read_key, " ", self.t.marker_wait_s, acq)
                    if pressed is None:
                        self.op.progress(
                            f"No SPACE within {self.t.marker_wait_s:.0f} s; moving on."
                        )
                    else:
                        acq.add_marker(Marker(pressed, "moment", "moment", "keyboard"))
                        captured.append(pressed)
                        self.op.progress(f"Marker {number} saved.")
                elif now >= next_progress:
                    counts = acq.counts()
                    rate = (counts[StreamKind.EEG] - last_counts[StreamKind.EEG]) / (now - last_t)
                    last_counts, last_t = counts, now
                    next_progress += self.t.progress_every_s
                    self.op.progress(self._progress_line(acq, now - start, rate))
                self._wait(min(TICK_S, max(0.0, end - now)), acq)
            session_dir = acq.session_dir
        session = self._load(session_dir, f"the {label}")
        self.sessions[label.capitalize()] = self._relative(session_dir)
        return [evaluate_record(session), evaluate_markers(session, captured, n)]

    def step_power(self) -> list[CheckResult]:
        self.op.say(
            "This checks that MuFuse recovers when the headband switches off. A short recording "
            "starts first. When I tell you, switch the headband OFF with its power button and "
            "keep it off until I say, then switch it back ON. Keep wearing it throughout."
        )
        self.op.wait_for_enter()
        outage: Pause | None = None
        resume_after: float | None = None
        note = ""
        with self._streaming("hardware test: power-off recovery") as acq:
            self.op.progress(f"Recording normally for {self.t.power_lead_s:.0f} s…")
            self._wait(self.t.power_lead_s, acq)
            pauses_before = len(acq.pauses())
            self.op.instruct("Switch the headband OFF now.")
            self.op.act(Action.POWER_OFF)
            stopped_at = self._wait_for_data_stop(acq)
            if stopped_at is None:
                note = (
                    f"The data never stopped within {self.t.power_detect_s:.0f} s, so the "
                    "headband probably stayed on."
                )
            else:
                self.op.progress("Data stopped. Keep the headband off.")
                remaining = stopped_at + self.t.power_off_s - self.clock()
                self.op.countdown(int(remaining), "Switch it back on in")
                self._wait(max(0.0, stopped_at + self.t.power_off_s - self.clock()), acq)
                self.op.instruct("Switch the headband back ON now.")
                on_at = self.clock()
                self.op.act(Action.POWER_ON)
                pause = self._wait_for_resume(acq, pauses_before)
                if pause is None:
                    note = (
                        f"Streaming did not come back within {self.t.resume_wait_s:.0f} s "
                        "of the power-on prompt."
                    )
                else:
                    outage = pause
                    resume_after = pause.resumed_at - on_at
                    self.op.progress(
                        f"Streaming resumed {resume_after:.1f} s after the power-on prompt. "
                        f"Recording {self.t.power_tail_s:.0f} s more…"
                    )
                    self._wait(self.t.power_tail_s, acq)
            session_dir = acq.session_dir
        session = self._load(session_dir, "the power-off recording")
        self.sessions["Power-off recording"] = self._relative(session_dir)
        return [evaluate_power(session, outage, resume_after, note)]

    def step_interrupt(self) -> list[CheckResult]:
        self.op.say(
            "Last check. A short recording starts. When I tell you, press Ctrl+C once: that "
            "stops it the same way it stops `mufuse record`."
        )
        self.op.wait_for_enter()
        interrupted = False
        acq = self._acquisition("hardware test: Ctrl+C")
        acq.start()
        try:
            self._wait(self.t.interrupt_lead_s, acq)
            self.op.instruct("Press Ctrl+C now (once).")
            try:
                self.op.act(Action.PRESS_CTRL_C)
                self._wait(self.t.interrupt_wait_s, acq)
            except KeyboardInterrupt:
                interrupted = True
                self.op.say("Ctrl+C received. Checking the saved recording…")
        finally:
            acq.stop()
        session_dir = acq.session_dir
        session = self._load(session_dir, "the Ctrl+C recording")
        self.sessions["Ctrl+C recording"] = self._relative(session_dir)
        note = "" if interrupted else f"No Ctrl+C arrived within {self.t.interrupt_wait_s:.0f} s"
        return [evaluate_interrupt(session, interrupted=interrupted, note=note)]

    # --- helpers ----------------------------------------------------------------------------

    def _device(self) -> FoundDevice:
        if self.device is None:  # pragma: no cover - the run stops when nothing is found
            raise StepError("No headband selected")
        return self.device

    def _acquisition(self, notes: str | None) -> BackgroundAcquisition:
        device, details = self._device(), self.details
        supervisor = StreamSupervisor(
            lambda: self.bench.make_source(device, details),
            stall_after=self.t.stall_after_s,
            backoff=self.t.backoff_s,
        )
        sessions = self.run_dir / "sessions"

        def new_writer(src: HeadbandSource) -> SessionWriter:
            return SessionWriter.create(sessions, src.device, src.streams, notes=notes or "")

        return BackgroundAcquisition(
            supervisor,
            writer_factory=None if notes is None else new_writer,
            poll_s=self.t.poll_s,
            pause_threshold_s=self.t.pause_threshold_s,
            clock=self.clock,
        )

    @contextmanager
    def _streaming(self, notes: str | None = None) -> Generator[BackgroundAcquisition]:
        acq = self._acquisition(notes)
        acq.start()
        try:
            yield acq
        finally:
            acq.stop()

    def _wait(self, seconds: float, acq: BackgroundAcquisition | None = None) -> None:
        deadline = self.clock() + seconds
        while True:
            if acq is not None and acq.error is not None:
                raise StepError(f"Acquisition stopped with an error: {acq.error}")
            remaining = deadline - self.clock()
            if remaining <= 0:
                return
            self.sleep(min(TICK_S, remaining))

    def _wait_for_key(
        self, read_key: KeyReader, wanted: str, timeout: float, acq: BackgroundAcquisition
    ) -> float | None:
        deadline = self.clock() + timeout
        while self.clock() < deadline:
            key = read_key()
            if key == wanted:
                return self.clock()
            if key is None:
                self._wait(min(0.01, self.t.poll_s), acq)
        return None

    def _wait_for_data_stop(self, acq: BackgroundAcquisition) -> float | None:
        deadline = self.clock() + self.t.power_detect_s
        while self.clock() < deadline:
            since = acq.seconds_since_data()
            if since is not None and (
                since > self.t.pause_threshold_s or acq.state is State.RECONNECTING
            ):
                return self.clock() - since
            self._wait(TICK_S, acq)
        return None

    def _wait_for_resume(self, acq: BackgroundAcquisition, pauses_before: int) -> Pause | None:
        deadline = self.clock() + self.t.resume_wait_s
        while self.clock() < deadline:
            pauses = acq.pauses()
            if len(pauses) > pauses_before:
                return pauses[pauses_before]
            self._wait(TICK_S, acq)
        return None

    def _time_one_connection(self) -> float | None:
        source = self.bench.make_source(self._device(), self.details)
        t0 = self.clock()
        try:
            source.start()
        except SourceError:
            return None
        try:
            deadline = t0 + self.t.connect_timeout_s
            while self.clock() < deadline:
                if any(c.kind is StreamKind.EEG and c.n_samples for c in source.read()):
                    return self.clock() - t0
                self.sleep(min(0.02, self.t.poll_s))
            return None
        except SourceError:
            return None
        finally:
            source.stop()

    def _progress_line(self, acq: BackgroundAcquisition, elapsed: float, rate: float) -> str:
        line = f"{_clock_text(elapsed)} of {_clock_text(self.t.record_s)} · EEG {rate:.0f}/s"
        battery = _battery(acq.latest(StreamKind.OPTICS))
        if battery is not None:
            line += f" · battery {battery:.0f}%"
        if acq.state is State.RECONNECTING:
            line += " · reconnecting"
        return line

    def _load(self, session_dir: Path | None, what: str) -> LoadedSession:
        if session_dir is None:  # pragma: no cover - every recording step creates a writer
            raise StepError(f"No session was written for {what}")
        try:
            return load_session(session_dir)
        except (OSError, ValueError, KeyError) as exc:
            raise StepError(f"Could not reload {what}: {exc}") from exc

    def _relative(self, path: Path | None) -> str:
        if path is None:  # pragma: no cover
            return ""
        try:
            return path.relative_to(self.run_dir).as_posix()
        except ValueError:  # pragma: no cover
            return str(path)


def _all_failed(step: Step, message: str) -> list[CheckResult]:
    return [result(key, False, message, "") for key in step.checks]


def _battery(optics_row: FloatArray | None) -> float | None:
    return None if optics_row is None else float(optics_row[-1])


def _clock_text(seconds: float) -> str:
    seconds = max(0, round(seconds))
    return f"{seconds // 60}:{seconds % 60:02d}"


def _duration(seconds: float) -> str:
    if seconds >= 60:
        minutes = seconds / 60
        return f"{minutes:g}-minute"
    return f"{seconds:g}-second"


def _about(seconds: float) -> str:
    if seconds < 60:
        return f"about {max(5, round(seconds / 5) * 5)} s"
    return f"about {max(1, round(seconds / 60))} min"


STEPS: tuple[Step, ...] = (
    Step(
        "find",
        CHECKS["find"].title,
        ("find",),
        HardwareTest.step_find,
        lambda t: t.scan_s + 5,
    ),
    Step(
        "firmware",
        CHECKS["firmware"].title,
        ("firmware",),
        HardwareTest.step_firmware,
        lambda t: t.info_timeout_s,
    ),
    Step(
        "streams",
        CHECKS["streams"].title,
        ("streams",),
        HardwareTest.step_streams,
        lambda t: t.settle_s + t.stream_s + 5,
    ),
    Step(
        "connect",
        CHECKS["connect"].title,
        ("connect",),
        HardwareTest.step_connect,
        lambda t: t.connect_attempts * (5 + t.connect_pause_s),
    ),
    Step(
        "contact",
        CHECKS["contact"].title,
        ("contact",),
        HardwareTest.step_contact,
        lambda t: (
            t.settle_s
            + t.rest_s
            + t.blink_s
            + t.clench_s
            + t.lift_s
            + 4 * (t.countdown_s + t.drain_s + t.recover_s)
        ),
    ),
    Step(
        "record",
        "{record} recording with markers",
        ("record", "markers"),
        HardwareTest.step_record,
        lambda t: t.record_s + 5,
    ),
    Step(
        "power",
        CHECKS["power"].title,
        ("power",),
        HardwareTest.step_power,
        lambda t: t.power_lead_s + t.power_off_s + 15 + t.power_tail_s,
    ),
    Step(
        "interrupt",
        CHECKS["interrupt"].title,
        ("interrupt",),
        HardwareTest.step_interrupt,
        lambda t: t.interrupt_lead_s + 10,
    ),
)
