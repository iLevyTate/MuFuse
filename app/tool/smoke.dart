// Talks to a running `mufuse serve`: prints the first messages, opens a check-in, answers it.
//
//   dart run tool/smoke.dart        (MUFUSE_SERVE_FILE may point at another serve.json)

import 'dart:async';
import 'dart:io';

import 'package:mufuse_strip/src/client.dart';
import 'package:mufuse_strip/src/serve_file.dart';

Future<void> main() async {
  final info = await readServeFile();
  if (info == null) {
    stderr.writeln('Engine not running: run `uv run mufuse serve`');
    exit(1);
  }
  final client = ServeClient(info);
  final seen = <String>[];
  final done = Completer<void>();
  late StreamSubscription<Map<String, dynamic>> sub;
  sub = client.events().listen((m) async {
    final type = '${m['type']}';
    seen.add(type);
    stdout.writeln('event $type');
    if (type == 'status' && !seen.contains('checkin') && seen.where((t) => t == 'status').length == 2) {
      stdout.writeln('command checkin -> ${(await client.command({'type': 'checkin'}))['type']}');
    }
    if (type == 'checkin') {
      final answers = m['answers'] as List;
      final reply = await client.command({'type': 'answer', 'id': m['id'], 'answer': answers.first});
      stdout.writeln('command answer ${answers.first} -> ${reply['type']}');
      if (!done.isCompleted) done.complete();
    }
    if (type == 'checkin_closed') stdout.writeln('closed answered=${m['answered']}');
  }, onError: (Object e) {
    if (!done.isCompleted) done.completeError(e);
  });
  await done.future.timeout(const Duration(seconds: 20));
  await sub.cancel();
  client.close();
  stdout.writeln('ok: ${seen.take(3).join(', ')} ...');
}
