import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:mufuse_strip/src/serve_file.dart';

void main() {
  test('each system finds serve.json where platformdirs puts the state folder', () {
    expect(serveFilePath(os: 'windows', env: {'LOCALAPPDATA': r'C:\Users\a\AppData\Local'}),
        r'C:\Users\a\AppData\Local\mufuse\serve.json');
    expect(serveFilePath(os: 'macos', env: {'HOME': '/Users/a'}),
        '/Users/a/Library/Application Support/mufuse/serve.json');
    expect(serveFilePath(os: 'linux', env: {'HOME': '/home/a'}), '/home/a/.local/state/mufuse/serve.json');
    expect(serveFilePath(os: 'linux', env: {'HOME': '/home/a', 'XDG_STATE_HOME': '/s'}), '/s/mufuse/serve.json');
  });

  test('MUFUSE_SERVE_FILE overrides the path', () {
    expect(serveFilePath(os: 'linux', env: {'MUFUSE_SERVE_FILE': '/tmp/s.json', 'HOME': '/h'}), '/tmp/s.json');
  });

  test('a serve file gives port and token; anything else gives nothing', () async {
    final dir = await Directory.systemTemp.createTemp('strip');
    final file = File('${dir.path}/serve.json');
    await file.writeAsString('{"v": 1, "port": 51234, "token": "abc", "pid": 9}');
    final info = await readServeFile(file.path);
    expect((info!.port, info.token), (51234, 'abc'));
    expect(await readServeFile('${dir.path}/missing.json'), isNull);
    expect(ServeInfo.parse('{"v": 2, "port": 1, "token": "t"}'), isNull);
    expect(ServeInfo.parse('not json'), isNull);
    await dir.delete(recursive: true);
  });
}
