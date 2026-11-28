import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mufuse_strip/src/controller.dart';
import 'package:mufuse_strip/src/serve_file.dart';
import 'package:mufuse_strip/src/strip_view.dart';

import 'examples.dart';

/// A replayed engine: messages are handed over one by one, commands are recorded.
class FakeLink implements EngineLink {
  final messages = StreamController<Map<String, dynamic>>();
  final sent = <Map<String, Object?>>[];

  @override
  Stream<Map<String, dynamic>> events() => messages.stream;

  @override
  Future<Map<String, dynamic>> command(Map<String, Object?> body) async {
    sent.add(body);
    return {'v': 1, 'type': 'ok'};
  }

  @override
  void close() {}
}

/// An engine that confirms a cloud switch the way `mufuse serve` does.
class CloudLink extends FakeLink {
  @override
  Future<Map<String, dynamic>> command(Map<String, Object?> body) async {
    sent.add(body);
    return {'v': 1, 'type': 'ok', if (body['type'] == 'cloud') 'cloud': body['on']};
  }
}

Widget host(StripController c) => MaterialApp(
      home: Scaffold(
        body: ListenableBuilder(
          listenable: c,
          builder: (_, _) => StripView(
            state: c.state,
            engineRunning: c.engineRunning,
            error: c.lastError,
            onCheckIn: c.checkIn,
            onMark: c.mark,
            onSnooze: c.snooze,
            onAnswer: c.answer,
            chatOpen: c.chatOpen,
            onChat: c.toggleChat,
            onAsk: c.ask,
            onCloud: c.setCloud,
          ),
        ),
      ),
    );

void main() {
  testWidgets('without an engine it says how to start one', (tester) async {
    final c = StripController(find: () async => null, retry: const Duration(milliseconds: 10));
    unawaited(c.run());
    await tester.pumpWidget(host(c));
    await tester.pump(const Duration(milliseconds: 20));
    expect(find.textContaining('Engine not running: run `uv run mufuse serve`'), findsOneWidget);
    c.dispose();
    await tester.pump(const Duration(milliseconds: 20));
  });

  testWidgets('the chat panel shows replies as sent, badges cloud ones, asks and switches cloud', (tester) async {
    final link = CloudLink();
    final c = StripController(
      find: () async => const ServeInfo(port: 1, token: 't', version: 1),
      connect: (_) => link,
    );
    unawaited(c.run());
    await tester.pumpWidget(host(c));
    link.messages
      ..add(example('hello'))
      ..add({...example('status'), 'sensors': {'AF7': 'good', 'AF8': 'good'}});
    await tester.pump();
    await tester.pump();
    expect(find.byKey(const Key('chat')), findsNothing);
    await tester.tap(find.text('chat'));
    await tester.pump();
    expect(find.byKey(const Key('chat')), findsOneWidget);

    final said = example('chat');
    link.messages
      ..add(said)
      ..add({...said, 'text': 'From the cloud model, as sent.', 'cloud': true, 'source': 'model'});
    await tester.pump();
    await tester.pump();
    expect(find.text(said['text'] as String), findsOneWidget);
    expect(find.text('From the cloud model, as sent.'), findsOneWidget);
    expect(find.byKey(const Key('cloud-badge')), findsOneWidget); // only the cloud line

    await tester.enterText(find.byKey(const Key('ask')), 'what are you seeing?');
    await tester.tap(find.byKey(const Key('ask-send')));
    await tester.pump();
    expect(link.sent.last, {'type': 'ask', 'text': 'what are you seeing?'});
    expect(find.text('what are you seeing?'), findsOneWidget); // the wearer's own line

    await tester.tap(find.byKey(const Key('cloud-switch')));
    await tester.pump();
    await tester.pump();
    expect(link.sent.last, {'type': 'cloud', 'on': true});
    expect(tester.widget<Switch>(find.byKey(const Key('cloud-switch'))).value, isTrue);
    c.dispose();
    await link.messages.close();
    await tester.pump();
  });

  testWidgets('a replayed session drives the strip and the check-in panel', (tester) async {
    final link = FakeLink();
    final c = StripController(
      find: () async => const ServeInfo(port: 1, token: 't', version: 1),
      connect: (_) => link,
    );
    unawaited(c.run());
    await tester.pumpWidget(host(c));
    link.messages
      ..add(example('hello'))
      ..add({
        ...example('status'),
        'sensors': {'AF7': 'good', 'AF8': 'none'},
        'line': 'fix AF8 first: no readings',
        'elapsed': 61.0,
      });
    await tester.pump();
    await tester.pump();
    expect(find.text('fix AF8'), findsOneWidget);
    expect(find.text('01:01'), findsOneWidget);
    expect(find.text('fix AF8 first: no readings'), findsOneWidget);
    final dot = tester.widget<Container>(find.byKey(const Key('dot')));
    expect((dot.decoration! as BoxDecoration).color, fairAmber);

    await tester.tap(find.text('mark'));
    await tester.tap(find.text('snooze'));
    await tester.pump();
    expect(link.sent.map((m) => m['type']), ['mark', 'snooze']);

    final asked = example('checkin');
    final answers = asked['answers'] as List;
    link.messages.add(asked);
    await tester.pump();
    await tester.pump();
    expect(find.byKey(const Key('checkin')), findsOneWidget);
    final shown = tester.widgetList<OutlinedButton>(find.byType(OutlinedButton)).map((b) => (b.child! as Text).data);
    expect(shown, answers);

    await tester.tap(find.byKey(Key('answer:${answers.first}')));
    await tester.pump();
    expect(link.sent.last, {'type': 'answer', 'id': asked['id'], 'answer': answers.first, 'text': null});

    await tester.tap(find.byKey(const Key('answer:own words')));
    await tester.pump();
    await tester.enterText(find.byKey(const Key('words')), 'the meeting at three');
    await tester.tap(find.byKey(const Key('send')));
    await tester.pump();
    expect(link.sent.last, {'type': 'answer', 'id': asked['id'], 'answer': 'own words', 'text': 'the meeting at three'});

    link.messages.add({...example('checkin_closed'), 'id': asked['id']});
    await tester.pump();
    await tester.pump();
    expect(find.byKey(const Key('checkin')), findsNothing);
    c.dispose();
    await link.messages.close();
    await tester.pump();
  });
}
