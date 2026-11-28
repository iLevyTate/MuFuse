import 'package:flutter_test/flutter_test.dart';
import 'package:mufuse_strip/src/strip_state.dart';

import 'examples.dart';

Map<String, dynamic> status(Map<String, String> sensors, {String line = 'blinks usual', Object? open}) => {
      ...example('status'),
      'sensors': sensors,
      'line': line,
      'link': 'streaming',
      'elapsed': 125.4,
      'open_checkin': open,
    };

void main() {
  test('every stored example is read without error', () {
    var s = const StripState();
    for (final type in ['hello', 'status', 'features', 'checkin', 'checkin_closed', 'session']) {
      s = reduce(s, example(type));
    }
    expect(s.connected, isTrue);
    expect(s.ended, isTrue);
  });

  test('hello connects and takes the device and question', () {
    final s = reduce(const StripState(), example('hello'));
    expect((s.connected, s.device, s.question), (true, 'SimulatedAthena', "What's on your mind?"));
  });

  test('status sets the clock and the line, word for word', () {
    final s = reduce(const StripState(), status({'AF7': 'good', 'AF8': 'good'}, line: 'blinks higher · alpha usual'));
    expect(s.clock, '02:05');
    expect(s.line, 'blinks higher · alpha usual');
    expect((s.quality, s.qualityText), (Quality.good, 'good signal'));
  });

  test('the dot grades the forehead signal and names the sensor to fix', () {
    StripState after(Map<String, String> sensors) => reduce(const StripState(), status(sensors));
    expect(after({'AF7': 'none', 'AF8': 'good'}).quality, Quality.fair);
    expect(after({'AF7': 'none', 'AF8': 'good'}).qualityText, 'fix AF7');
    expect(after({'AF7': 'noisy', 'AF8': 'none'}).quality, Quality.poor);
    expect(after({'AF7': 'noisy', 'AF8': 'none'}).qualityText, 'fix AF8');
    expect(after({'AF7': 'settling', 'AF8': 'noisy'}).quality, Quality.fair);
    expect(after({}).quality, Quality.waiting);
    // The ear sensors never change the dot (issue #12).
    expect(after({'TP9': 'none', 'AF7': 'good', 'AF8': 'good', 'TP10': 'none'}).quality, Quality.good);
  });

  test('a check-in opens with its answers in the order sent, and closes on its own id only', () {
    final asked = example('checkin');
    var s = reduce(const StripState(connected: true), asked);
    expect(s.checkin!.answers, asked['answers']);
    s = reduce(s, {'v': 1, 'type': 'checkin_closed', 'id': -1, 'answered': true});
    expect(s.checkin, isNotNull);
    s = reduce(s, {...example('checkin_closed'), 'id': asked['id']});
    expect(s.checkin, isNull);
  });

  test('a status without an open check-in clears a missed close', () {
    var s = reduce(const StripState(connected: true), example('checkin'));
    s = reduce(s, status({'AF7': 'good', 'AF8': 'good'}, open: s.checkin!.id));
    expect(s.checkin, isNotNull);
    s = reduce(s, status({'AF7': 'good', 'AF8': 'good'}));
    expect(s.checkin, isNull);
  });

  test('another version or an unknown type changes nothing', () {
    const s = StripState(connected: true, line: 'x');
    expect(identical(reduce(s, {'v': 2, 'type': 'hello'}), s), isTrue);
    expect(identical(reduce(s, {'v': 1, 'type': 'dance'}), s), isTrue);
  });

  test('a long session shows hours', () {
    expect(const StripState(elapsed: 3725).clock, '1:02:05');
  });
}
