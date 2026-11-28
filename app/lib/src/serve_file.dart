// Where `mufuse serve` leaves its port and token: `serve.json` in the folder that Python's
// platformdirs gives for user_state_path("mufuse", appauthor=False) on each system.

import 'dart:convert';
import 'dart:io';

/// The port and token of the running engine.
class ServeInfo {
  const ServeInfo({required this.port, required this.token, required this.version});

  final int port;
  final String token;
  final int version;

  /// What `serve.json` holds, or null when it is not a serve file of a version this app reads.
  static ServeInfo? parse(String text) {
    try {
      final raw = jsonDecode(text);
      if (raw is! Map<String, dynamic>) return null;
      final port = raw['port'];
      final token = raw['token'];
      final version = raw['v'];
      if (port is! int || token is! String || version != 1) return null;
      return ServeInfo(port: port, token: token, version: version as int);
    } on FormatException {
      return null;
    }
  }
}

/// The path of `serve.json` for the system `os` (Platform.operatingSystem's names).
///
/// `MUFUSE_SERVE_FILE` overrides it. Windows: %LOCALAPPDATA%\mufuse; macOS:
/// ~/Library/Application Support/mufuse; Linux and others: $XDG_STATE_HOME/mufuse, else
/// ~/.local/state/mufuse.
String serveFilePath({required String os, required Map<String, String> env}) {
  final override = env['MUFUSE_SERVE_FILE'];
  if (override != null && override.isNotEmpty) return override;
  final home = env['HOME'] ?? env['USERPROFILE'] ?? '';
  switch (os) {
    case 'windows':
      final local = env['LOCALAPPDATA'] ?? '$home\\AppData\\Local';
      return '$local\\mufuse\\serve.json';
    case 'macos':
      return '$home/Library/Application Support/mufuse/serve.json';
    default:
      final xdg = env['XDG_STATE_HOME'];
      final state = (xdg != null && xdg.isNotEmpty) ? xdg : '$home/.local/state';
      return '$state/mufuse/serve.json';
  }
}

/// The running engine's port and token on this machine, or null when none is running.
Future<ServeInfo?> readServeFile([String? path]) async {
  final file = File(
    path ?? serveFilePath(os: Platform.operatingSystem, env: Platform.environment),
  );
  if (!await file.exists()) return null;
  return ServeInfo.parse(await file.readAsString());
}
