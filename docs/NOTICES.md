# Third-party models

MuFuse ships no model files. `uv run mufuse voice fetch` downloads these, pinned by sha256, from the
sherpa-onnx releases (k2-fsa/sherpa-onnx, Apache-2.0) into the user data folder.

| Model | Used for | Licence | By |
|---|---|---|---|
| Silero VAD (`silero_vad.onnx`) | where a spoken turn ends | MIT | Silero Team |
| Moonshine base / tiny English, quantized 2026-02-27 | speech to text | MIT | Moonshine AI (Useful Sensors) |
| Pocket TTS int8 2026-01-26 | text to speech | CC-BY-4.0 | Kyutai |

**Attribution (CC-BY-4.0):** the voice is generated with Pocket TTS by Kyutai
(https://huggingface.co/kyutai/pocket-tts), converted to ONNX by the sherpa-onnx project. MuFuse
uses it unchanged; the default voice is the first reference recording shipped in that package.
Licence: https://creativecommons.org/licenses/by/4.0/
