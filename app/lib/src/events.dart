// A Server-Sent Events parser: text in, whole events out, however the text is split.

import 'dart:convert';

class SseEvent {
  const SseEvent(this.event, this.data);

  final String event;
  final String data;

  /// The JSON message the event carries, or null when it is not a JSON object.
  Map<String, dynamic>? get message {
    try {
      final decoded = jsonDecode(data);
      return decoded is Map<String, dynamic> ? decoded : null;
    } on FormatException {
      return null;
    }
  }
}

class SseParser {
  String _buffer = '';
  String _event = 'message';
  final List<String> _data = [];

  /// Feed the next piece of the stream; returns every event it completes.
  List<SseEvent> add(String chunk) {
    _buffer += chunk;
    final out = <SseEvent>[];
    while (true) {
      final end = _buffer.indexOf('\n');
      if (end < 0) break;
      var line = _buffer.substring(0, end);
      _buffer = _buffer.substring(end + 1);
      if (line.endsWith('\r')) line = line.substring(0, line.length - 1);
      if (line.isEmpty) {
        if (_data.isNotEmpty) out.add(SseEvent(_event, _data.join('\n')));
        _event = 'message';
        _data.clear();
      } else if (line.startsWith(':')) {
        continue; // a comment: the server's heartbeat
      } else {
        final colon = line.indexOf(':');
        final field = colon < 0 ? line : line.substring(0, colon);
        var value = colon < 0 ? '' : line.substring(colon + 1);
        if (value.startsWith(' ')) value = value.substring(1);
        if (field == 'event') _event = value;
        if (field == 'data') _data.add(value);
      }
    }
    return out;
  }
}
