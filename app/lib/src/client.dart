// The only way the app talks to the engine: `mufuse serve` on 127.0.0.1, with its token.

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'events.dart';
import 'serve_file.dart';

class ServeClient {
  ServeClient(this.info, {HttpClient? http}) : _http = http ?? HttpClient();

  final ServeInfo info;
  final HttpClient _http;

  Uri _uri(String path) => Uri(scheme: 'http', host: '127.0.0.1', port: info.port, path: path);

  void _headers(HttpClientRequest request) {
    request.headers.set(HttpHeaders.hostHeader, '127.0.0.1:${info.port}');
    request.headers.set(HttpHeaders.authorizationHeader, 'Bearer ${info.token}');
  }

  /// The engine's messages, in order, until the stream ends or the connection fails.
  Stream<Map<String, dynamic>> events() async* {
    final request = await _http.getUrl(_uri('/events'));
    _headers(request);
    request.headers.set(HttpHeaders.acceptHeader, 'text/event-stream');
    final response = await request.close();
    if (response.statusCode != 200) {
      await response.drain<void>();
      throw HttpException('events: HTTP ${response.statusCode}');
    }
    final parser = SseParser();
    await for (final text in response.transform(utf8.decoder)) {
      for (final event in parser.add(text)) {
        final message = event.message;
        if (message != null) yield message;
      }
    }
  }

  /// Send one command; the engine's reply (`ok` or `error` with a reason).
  Future<Map<String, dynamic>> command(Map<String, Object?> body) async {
    final request = await _http.postUrl(_uri('/command'));
    _headers(request);
    request.headers.contentType = ContentType.json;
    // A known length, never chunked: the engine reads exactly Content-Length bytes.
    final bytes = utf8.encode(jsonEncode(body));
    request.contentLength = bytes.length;
    request.add(bytes);
    final response = await request.close();
    final text = await response.transform(utf8.decoder).join();
    final decoded = jsonDecode(text.isEmpty ? '{}' : text);
    return decoded is Map<String, dynamic> ? decoded : {'type': 'error', 'error': 'no reply'};
  }

  void close() => _http.close(force: true);
}
