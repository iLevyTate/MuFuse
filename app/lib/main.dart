// The MuFuse desk strip: a thin always-on-top window that talks only to `mufuse serve`.
//
// Size and always-on-top are set by each platform's runner (windows/runner/main.cpp,
// linux/runner/my_application.cc, macos/Runner/MainFlutterWindow.swift), with no plugin.

import 'package:flutter/material.dart';

import 'src/controller.dart';
import 'src/strip_view.dart';

void main() {
  final controller = StripController();
  controller.run();
  runApp(StripApp(controller: controller));
}

class StripApp extends StatelessWidget {
  const StripApp({super.key, required this.controller});

  final StripController controller;

  @override
  Widget build(BuildContext context) => MaterialApp(
        title: 'MuFuse strip',
        debugShowCheckedModeBanner: false,
        theme: ThemeData(brightness: Brightness.dark, scaffoldBackgroundColor: labSlate),
        home: Scaffold(
          body: Align(
            alignment: Alignment.topCenter,
            child: ListenableBuilder(
              listenable: controller,
              builder: (context, _) => StripView(
                state: controller.state,
                engineRunning: controller.engineRunning,
                error: controller.lastError,
                onCheckIn: controller.checkIn,
                onMark: controller.mark,
                onSnooze: controller.snooze,
                onAnswer: controller.answer,
              ),
            ),
          ),
        ),
      );
}
