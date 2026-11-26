# Contract: HeadbandSource

```python
class HeadbandSource(Protocol):
    @property
    def device(self) -> DeviceInfo: ...
    @property
    def streams(self) -> Mapping[StreamKind, StreamSpec]: ...
    def start(self) -> None: ...  # connect + begin streaming; raises SourceError
    def read(
        self,
    ) -> list[
        Chunk
    ]: ...  # non-blocking; all samples since last read (possibly empty chunks omitted)
    def stop(self) -> None: ...  # idempotent; releases device
```

Guarantees: identical `streams` layout for real, simulated and playback Athena sources; timestamps on the session
clock (UNIX seconds); `read()` never blocks > 10 ms; `stop()` safe to call after errors.
