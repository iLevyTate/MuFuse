// The strip and the check-in panel. Plain widgets: state in, callbacks out.

import 'package:flutter/material.dart';

import 'strip_state.dart';

// Brand tokens (docs/BRAND.md). Status colours grade the signal only, never the person.
const labSlate = Color(0xFF111315);
const benchPaper = Color(0xFFF3F1EC);
const graticule = Color(0xFF2A2F36);
const phosphorAmber = Color(0xFFF59E0B);
const scopeGreen = Color(0xFF22C55E);
const clipRed = Color(0xFFEF4444);
const fairAmber = Color(0xFFEAB308);
const dim = Color(0xFF8B949E);

const ownWords = 'own words';
const startCommand = 'uv run mufuse serve';

Color qualityColour(Quality q) => switch (q) {
      Quality.good => scopeGreen,
      Quality.fair => fairAmber,
      Quality.poor => clipRed,
      Quality.waiting => dim,
    };

class StripView extends StatelessWidget {
  const StripView({
    super.key,
    required this.state,
    required this.engineRunning,
    required this.onCheckIn,
    required this.onMark,
    required this.onSnooze,
    required this.onAnswer,
    this.error,
  });

  final StripState state;
  final bool engineRunning;
  final VoidCallback onCheckIn;
  final VoidCallback onMark;
  final VoidCallback onSnooze;
  final void Function(int id, String answer, String? text) onAnswer;
  final String? error;

  @override
  Widget build(BuildContext context) {
    final checkin = state.checkin;
    return Container(
      decoration: BoxDecoration(color: labSlate, border: Border.all(color: graticule)),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        mainAxisSize: MainAxisSize.min,
        children: [
          SizedBox(height: 40, child: engineRunning ? _line() : _missing()),
          if (checkin != null) CheckinPanel(checkin: checkin, onAnswer: onAnswer),
        ],
      ),
    );
  }

  Widget _missing() => const Padding(
        padding: EdgeInsets.symmetric(horizontal: 12),
        child: Row(children: [
          _Dot(colour: dim),
          SizedBox(width: 8),
          Expanded(
            child: Text(
              'Engine not running: run `$startCommand`',
              key: Key('missing'),
              overflow: TextOverflow.ellipsis,
              style: TextStyle(color: benchPaper, fontSize: 13),
            ),
          ),
        ]),
      );

  Widget _line() {
    const text = TextStyle(color: benchPaper, fontSize: 13);
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12),
      child: Row(children: [
        _Dot(colour: qualityColour(state.quality)),
        const SizedBox(width: 8),
        Text(state.qualityText, key: const Key('quality'), style: text),
        const SizedBox(width: 14),
        Text(state.clock, key: const Key('clock'), style: text.copyWith(fontFeatures: const [FontFeature.tabularFigures()])),
        const SizedBox(width: 14),
        Expanded(
          child: Text(
            error ?? state.line,
            key: const Key('line'),
            overflow: TextOverflow.ellipsis,
            style: text.copyWith(color: error == null ? benchPaper : fairAmber),
          ),
        ),
        _Button('check in', onCheckIn, enabled: state.checkin == null),
        _Button('mark', onMark),
        _Button(state.snoozed ? 'snoozed' : 'snooze', onSnooze, enabled: !state.snoozed),
      ]),
    );
  }
}

class _Dot extends StatelessWidget {
  const _Dot({required this.colour});
  final Color colour;

  @override
  Widget build(BuildContext context) => Container(
        key: const Key('dot'),
        width: 10,
        height: 10,
        decoration: BoxDecoration(color: colour, shape: BoxShape.circle),
      );
}

class _Button extends StatelessWidget {
  const _Button(this.label, this.onPressed, {this.enabled = true});
  final String label;
  final VoidCallback onPressed;
  final bool enabled;

  @override
  Widget build(BuildContext context) => TextButton(
        onPressed: enabled ? onPressed : null,
        style: TextButton.styleFrom(
          foregroundColor: phosphorAmber,
          disabledForegroundColor: dim,
          padding: const EdgeInsets.symmetric(horizontal: 8),
          minimumSize: const Size(0, 30),
        ),
        child: Text(label),
      );
}

class CheckinPanel extends StatefulWidget {
  const CheckinPanel({super.key, required this.checkin, required this.onAnswer});

  final CheckinView checkin;
  final void Function(int id, String answer, String? text) onAnswer;

  @override
  State<CheckinPanel> createState() => _CheckinPanelState();
}

class _CheckinPanelState extends State<CheckinPanel> {
  bool _writing = false;
  final _words = TextEditingController();

  @override
  void dispose() {
    _words.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final c = widget.checkin;
    return Container(
      key: const Key('checkin'),
      padding: const EdgeInsets.fromLTRB(12, 8, 12, 12),
      decoration: const BoxDecoration(border: Border(top: BorderSide(color: graticule))),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(c.question, style: const TextStyle(color: benchPaper, fontSize: 15)),
          const SizedBox(height: 8),
          Wrap(spacing: 6, runSpacing: 6, children: [
            for (final a in c.answers)
              OutlinedButton(
                key: Key('answer:$a'),
                onPressed: () => a == ownWords ? setState(() => _writing = true) : widget.onAnswer(c.id, a, null),
                style: OutlinedButton.styleFrom(
                  foregroundColor: benchPaper,
                  side: const BorderSide(color: graticule),
                  minimumSize: const Size(0, 30),
                ),
                child: Text(a),
              ),
          ]),
          if (_writing) ...[
            const SizedBox(height: 8),
            Row(children: [
              Expanded(
                child: TextField(
                  key: const Key('words'),
                  controller: _words,
                  autofocus: true,
                  style: const TextStyle(color: benchPaper),
                  decoration: const InputDecoration(isDense: true, hintText: 'in your own words'),
                  onSubmitted: (_) => _send(),
                ),
              ),
              TextButton(key: const Key('send'), onPressed: _send, child: const Text('send')),
            ]),
          ],
        ],
      ),
    );
  }

  void _send() {
    final text = _words.text.trim();
    if (text.isEmpty) return;
    widget.onAnswer(widget.checkin.id, ownWords, text);
  }
}
