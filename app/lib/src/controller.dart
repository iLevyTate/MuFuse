// Keeps the strip connected to the engine: finds serve.json, follows the events, retries.

import 'dart:async';

import 'package:flutter/foundation.dart';

import 'client.dart';
import 'serve_file.dart';
import 'strip_state.dart';

typedef FindEngine = Future<ServeInfo?> Function();
typedef Connect = EngineLink Function(ServeInfo info);

/// What the controller needs from a connection; `ServeClient` in the app, a fake in tests.
abstract class EngineLink {
  Stream<Map<String, dynamic>> events();
  Future<Map<String, dynamic>> command(Map<String, Object?> body);
  void close();
}

class _ClientLink implements EngineLink {
  _ClientLink(ServeInfo info) : _client = ServeClient(info);
  final ServeClient _client;
  @override
  Stream<Map<String, dynamic>> events() => _client.events();
  @override
  Future<Map<String, dynamic>> command(Map<String, Object?> body) => _client.command(body);
  @override
  void close() => _client.close();
}

class StripController extends ChangeNotifier {
  StripController({FindEngine? find, Connect? connect, this.retry = const Duration(seconds: 3)})
      : _find = find ?? readServeFile,
        _connect = connect ?? _ClientLink.new;

  final FindEngine _find;
  final Connect _connect;
  final Duration retry;

  StripState state = const StripState();
  bool engineRunning = false;
  String? lastError;
  EngineLink? _link;
  bool _stopped = false;

  /// Runs until `dispose`: connect, follow, and on any failure wait `retry` and start again.
  Future<void> run() async {
    while (!_stopped) {
      final info = await _find();
      if (info != null && !_stopped) {
        final link = _connect(info);
        _link = link;
        try {
          await for (final message in link.events()) {
            if (_stopped) break;
            engineRunning = true;
            state = reduce(state, message);
            notifyListeners();
          }
        } catch (_) {
          // Refused, reset or gone: the engine is not (or no longer) there.
        } finally {
          link.close();
          _link = null;
        }
      }
      if (_stopped) break;
      engineRunning = false;
      state = const StripState();
      notifyListeners();
      await Future<void>.delayed(retry);
    }
  }

  /// Send a command; null when it went through, else the reason it did not.
  Future<String?> send(Map<String, Object?> body) async {
    final link = _link;
    if (link == null) return 'not connected';
    try {
      final reply = await link.command(body);
      lastError = reply['type'] == 'ok' ? null : '${reply['error'] ?? 'refused'}';
    } catch (e) {
      lastError = 'not connected';
    }
    notifyListeners();
    return lastError;
  }

  Future<String?> checkIn() => send({'type': 'checkin'});
  Future<String?> mark() => send({'type': 'mark', 'label': 'moment'});
  Future<String?> snooze() => send({'type': 'snooze'});
  Future<String?> answer(int id, String answer, [String? text]) =>
      send({'type': 'answer', 'id': id, 'answer': answer, 'text': text});

  @override
  void dispose() {
    _stopped = true;
    _link?.close();
    super.dispose();
  }
}
