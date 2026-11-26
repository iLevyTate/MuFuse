"""Everything the guided test touches outside itself: the headband, the scan, the person."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from mufuse.acquisition.athena import DEFAULT_PRESET
from mufuse.acquisition.source import HeadbandSource
from mufuse.acquisition.types import FoundDevice
from mufuse.hwtest.operator import HumanOperator, Operator


@dataclass(frozen=True)
class DeviceDetails:
    """What the firmware query returned, carried into every recording's manifest."""

    firmware: str | None = None
    extra: dict[str, str] = field(default_factory=dict[str, str])


@dataclass(frozen=True)
class Bench:
    operator: Operator
    scan: Callable[[float], list[FoundDevice]]
    read_info: Callable[[FoundDevice, float], dict[str, str]]  # raises DeviceInfoError
    make_source: Callable[[FoundDevice, DeviceDetails], HeadbandSource]
    remember: Callable[[FoundDevice], None]
    saved_device: str | None
    description: str
    preset: str = DEFAULT_PRESET
    simulated: bool = False


def pick_device(found: Sequence[FoundDevice], saved: str | None) -> FoundDevice:
    """The saved headband when it is in range, otherwise the strongest signal (spec edge case)."""
    for device in found:
        if saved and device.name == saved:
            return device
    return max(found, key=lambda d: d.rssi)


def athena_bench(operator: HumanOperator, preset: str) -> Bench:  # pragma: no cover - hardware
    """The real headband through BrainFlow, with the firmware read over BLE first."""
    from importlib.metadata import version

    from mufuse.acquisition.brainflow_athena import BrainFlowAthena
    from mufuse.acquisition.discovery import read_device_info, scan_for_muse
    from mufuse.config import load_config, save_config

    def remember(device: FoundDevice) -> None:
        config = load_config()
        config.last_device_name, config.last_device_address = device.name, device.address
        save_config(config)

    def make_source(device: FoundDevice, details: DeviceDetails) -> HeadbandSource:
        return BrainFlowAthena(
            device_name=device.name,
            preset=preset,
            firmware=details.firmware,
            device_extra=details.extra,
        )

    return Bench(
        operator=operator,
        scan=scan_for_muse,
        read_info=lambda device, timeout: read_device_info(
            name=device.name, address=device.address, timeout_s=timeout
        ),
        make_source=make_source,
        remember=remember,
        saved_device=load_config().last_device_name,
        description=f"Muse S Athena via BrainFlow {version('brainflow')}",
        preset=preset,
    )
