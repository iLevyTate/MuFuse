# MuFuse desk strip

A thin, always-on-top window for desk sessions (feature 005, `specs/005-labelling-loop/README.md`).
It shows the signal quality dot, the session time and the engine's "now against your baseline"
line, and has buttons: check in, chat, mark, snooze. When the engine asks "What's on your mind?",
a panel opens with one-tap answers in the order the engine sent.

It talks only to `mufuse serve` on this computer, using the port and token the engine writes to
`serve.json` (`MUFUSE_SERVE_FILE` overrides where it looks). It has no runtime packages beyond
Flutter itself.

```bash
uv run mufuse serve --source sim     # or --source athena with the headband on
cd app && flutter run -d windows     # or -d macos / -d linux
```

The chat panel (feature 007) shows the engine's replies exactly as sent, your own lines, an input
box and a cloud-model switch; every reply that came from a cloud model carries a "cloud" badge.

Without the engine, the strip says so and tries again every few seconds.

- `lib/src/`: `serve_file.dart` (where serve.json lives on each system), `events.dart` (the
  Server-Sent Events parser), `strip_state.dart` (messages → what is shown), `client.dart`,
  `controller.dart`, `strip_view.dart`.
- Window size and always-on-top come from each platform's runner (`windows/runner/main.cpp`,
  `linux/runner/my_application.cc`, `macos/Runner/MainFlutterWindow.swift`).
- `flutter test` replays the engine's stored messages (`../tests/data/serve_messages/`).
- `dart run tool/smoke.dart` checks a running engine end to end: it opens a check-in, answers it and asks one chat question.
