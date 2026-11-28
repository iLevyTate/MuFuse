// What the strip shows, reduced from the engine's messages (src/mufuse/companion/serve.py).
// Words about the signal come from the engine (`status.line`) and are shown as they are.

/// How good the signal is. It grades the signal only, never the person (docs/BRAND.md).
enum Quality { waiting, good, fair, poor }

class CheckinView {
  const CheckinView({required this.id, required this.question, required this.answers, required this.source});

  final int id;
  final String question;
  final List<String> answers;
  final String source;
}

/// One line of the chat. `text` is shown exactly as it came: never re-worded in Dart.
class ChatLine {
  const ChatLine({required this.role, required this.text, this.source = '', this.model, this.cloud = false, this.t = 0});

  /// From a `chat` message of the engine.
  factory ChatLine.of(Map<String, dynamic> m) => ChatLine(
        role: (m['role'] as String?) ?? 'assistant',
        text: (m['text'] as String?) ?? '',
        source: (m['source'] as String?) ?? '',
        model: m['model'] as String?,
        cloud: m['cloud'] == true,
        t: (m['t'] as num?)?.toDouble() ?? 0,
      );

  final String role; // 'assistant' from the engine, 'you' for what the wearer typed
  final String text;
  final String source;
  final String? model;
  final bool cloud; // the words came from a cloud model: always shown with a badge
  final double t;
}

class StripState {
  const StripState({
    this.connected = false,
    this.device,
    this.question = "What's on your mind?",
    this.elapsed = 0,
    this.link = '',
    this.sensors = const {},
    this.line = '',
    this.snoozed = false,
    this.focus = false,
    this.checkin,
    this.ended = false,
    this.chat = const [],
    this.cloud = false,
  });

  final bool connected;
  final String? device;
  final String question;
  final double elapsed;
  final String link;
  final Map<String, String> sensors;
  final String line;
  final bool snoozed;
  final bool focus;
  final CheckinView? checkin;
  final bool ended;
  final List<ChatLine> chat;
  final bool cloud; // whether the cloud model is switched on

  static const chatKept = 100;
  static const forehead = ['AF7', 'AF8'];
  static const _rank = {'none': 0, 'noisy': 1, 'settling': 2, 'good': 3};

  Quality get quality {
    if (!connected || sensors.isEmpty) return Quality.waiting;
    if (link.isNotEmpty && link != 'streaming') return Quality.poor;
    final good = forehead.where((s) => sensors[s] == 'good').length;
    if (good == 2) return Quality.good;
    if (good == 1) return Quality.fair;
    final anyOff = forehead.any((s) => (sensors[s] ?? 'none') == 'none');
    return anyOff ? Quality.poor : Quality.fair;
  }

  /// A few words next to the dot: which sensor to fix, or that the signal is good.
  String get qualityText {
    if (!connected) return 'not connected';
    if (link.isNotEmpty && link != 'streaming') return link;
    if (sensors.isEmpty) return 'waiting for signal';
    final out = forehead.where((s) => sensors[s] != 'good').toList()
      ..sort((a, b) => (_rank[sensors[a]] ?? 0).compareTo(_rank[sensors[b]] ?? 0));
    return out.isEmpty ? 'good signal' : 'fix ${out.first}';
  }

  String get clock {
    final whole = elapsed < 0 ? 0 : elapsed.floor();
    final h = whole ~/ 3600;
    final m = (whole % 3600) ~/ 60;
    final s = whole % 60;
    String two(int n) => n.toString().padLeft(2, '0');
    return h > 0 ? '$h:${two(m)}:${two(s)}' : '${two(m)}:${two(s)}';
  }

  StripState copyWith({
    bool? connected,
    String? device,
    String? question,
    double? elapsed,
    String? link,
    Map<String, String>? sensors,
    String? line,
    bool? snoozed,
    bool? focus,
    CheckinView? Function()? checkin,
    bool? ended,
    List<ChatLine>? chat,
    bool? cloud,
  }) =>
      StripState(
        connected: connected ?? this.connected,
        device: device ?? this.device,
        question: question ?? this.question,
        elapsed: elapsed ?? this.elapsed,
        link: link ?? this.link,
        sensors: sensors ?? this.sensors,
        line: line ?? this.line,
        snoozed: snoozed ?? this.snoozed,
        focus: focus ?? this.focus,
        checkin: checkin != null ? checkin() : this.checkin,
        ended: ended ?? this.ended,
        chat: chat ?? this.chat,
        cloud: cloud ?? this.cloud,
      );

  /// The state with one more chat line, keeping the newest `chatKept`.
  StripState withLine(ChatLine line) {
    final all = [...chat, line];
    return copyWith(chat: all.length > chatKept ? all.sublist(all.length - chatKept) : all);
  }
}

/// The state after one message. Messages of another version or of an unknown type change nothing.
StripState reduce(StripState s, Map<String, dynamic> m) {
  if (m['v'] != 1) return s;
  switch (m['type']) {
    case 'hello':
      return s.copyWith(
        connected: true,
        ended: false,
        device: m['device'] as String?,
        question: (m['question'] as String?) ?? s.question,
        cloud: m['cloud'] is bool ? m['cloud'] as bool : s.cloud,
      );
    case 'status':
      final sensors = <String, String>{};
      final raw = m['sensors'];
      if (raw is Map) {
        raw.forEach((k, v) => sensors['$k'] = '$v');
      }
      final open = m['open_checkin'];
      return s.copyWith(
        connected: true,
        elapsed: (m['elapsed'] as num?)?.toDouble() ?? s.elapsed,
        link: (m['link'] as String?) ?? s.link,
        sensors: sensors,
        line: (m['line'] as String?) ?? s.line,
        snoozed: m['snoozed'] == true,
        focus: m['focus'] == true,
        // A check-in the engine no longer holds open is gone, whatever message was missed.
        checkin: open == null ? () => null : null,
      );
    case 'checkin':
      return s.copyWith(
        checkin: () => CheckinView(
          id: m['id'] as int,
          question: (m['question'] as String?) ?? s.question,
          answers: [for (final a in (m['answers'] as List? ?? const [])) '$a'],
          source: (m['source'] as String?) ?? '',
        ),
      );
    case 'checkin_closed':
      return s.checkin?.id == m['id'] ? s.copyWith(checkin: () => null) : s;
    case 'chat':
      return s.withLine(ChatLine.of(m));
    case 'session':
      return m['state'] == 'ended' ? s.copyWith(ended: true, checkin: () => null) : s;
    default:
      return s;
  }
}
