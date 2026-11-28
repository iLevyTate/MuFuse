import 'package:flutter_test/flutter_test.dart';
import 'package:mufuse_strip/src/events.dart';

void main() {
  test('an event split anywhere comes out whole', () {
    const text = 'event: hello\ndata: {"v": 1, "type": "hello"}\n\nevent: status\ndata: {"v": 1}\n\n';
    for (var cut = 0; cut < text.length; cut++) {
      final p = SseParser();
      final events = [...p.add(text.substring(0, cut)), ...p.add(text.substring(cut))];
      expect(events.map((e) => e.event), ['hello', 'status'], reason: 'cut at $cut');
      expect(events.first.message, {'v': 1, 'type': 'hello'});
    }
  });

  test('heartbeat comments and carriage returns are ignored', () {
    final events = SseParser().add(': still here\r\n\r\nevent: x\r\ndata: {"a": 1}\r\n\r\n');
    expect(events.single.event, 'x');
    expect(events.single.message, {'a': 1});
  });

  test('several data lines join with a newline; an event without a name is "message"', () {
    final e = SseParser().add('data: one\ndata: two\n\n').single;
    expect((e.event, e.data), ('message', 'one\ntwo'));
    expect(e.message, isNull);
  });
}
