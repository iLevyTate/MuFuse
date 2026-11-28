// The stored message examples of `mufuse serve` (tests/data/serve_messages/), read from the repo.

import 'dart:convert';
import 'dart:io';

final examplesDir = Directory('../tests/data/serve_messages');

Map<String, dynamic> example(String type) =>
    jsonDecode(File('${examplesDir.path}/$type.json').readAsStringSync()) as Map<String, dynamic>;
