"""
speech_engine.py - Offline speech wrappers for Shelly the Virtual Waiter.

Two responsibilities:
  * Text-to-Speech (TTS) via pyttsx3 (Windows SAPI5).
  * Speech-to-Text (STT) via faster-whisper (base.en, CPU, int8).

Design notes
------------
* Both backends are lazy-loaded. Importing this module does NOT download
  the Whisper model or initialize SAPI.
* STT model: ~145 MB. Downloaded on first use via huggingface-hub.
  Cached under %USERPROFILE%\\.cache\\huggingface\\hub. First use needs
  internet; subsequent runs are offline.
* WAV files are decoded with the stdlib `wave` module and passed to
  faster-whisper as a numpy float32 array at 16 kHz. This bypasses
  faster-whisper's internal PyAV call, so an incompatible `av` version
  does not break STT.
* The initial_prompt passed to Whisper biases recognition toward the
  restaurant vocabulary, so "Adobo" and "Sinigang" are less likely to be
  transcribed as "a bowl" or "sunny gang".
* Prices written as ₱N.NN are rewritten as "N.NN pesos" before TTS so
  Windows SAPI5 reads them naturally.
"""
from __future__ import annotations
import os
import re
import wave
from typing import Iterable, Optional

import numpy as np


TARGET_SAMPLE_RATE = 16000


class SpeechEngine:
    def __init__(
        self,
        whisper_model_size: str = "base.en",
        whisper_device: str = "cpu",
        whisper_compute_type: str = "int8",
        tts_rate: int = 180,
        tts_voice: Optional[str] = None,
    ):
        self._whisper_model_size = whisper_model_size
        self._whisper_device = whisper_device
        self._whisper_compute_type = whisper_compute_type
        self._whisper_model = None
        self._menu_prompt: Optional[str] = None
        self._tts_rate = tts_rate
        self._tts_voice = tts_voice

    # ---------- STT ----------
    def set_menu_prompt(self, item_names: Iterable[str]) -> None:
        names = [n.strip() for n in item_names if n and n.strip()]
        self._menu_prompt = (
            "Restaurant menu items: " + ", ".join(names) + "."
            if names else None
        )

    def _get_whisper(self):
        if self._whisper_model is None:
            from faster_whisper import WhisperModel
            self._whisper_model = WhisperModel(
                self._whisper_model_size,
                device=self._whisper_device,
                compute_type=self._whisper_compute_type,
            )
        return self._whisper_model

    @staticmethod
    def _decode_wav_to_array(path: str) -> np.ndarray:
        """Read a WAV file and return float32 mono audio at 16 kHz."""
        with wave.open(path, "rb") as wf:
            n_channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            framerate = wf.getframerate()
            n_frames = wf.getnframes()
            raw = wf.readframes(n_frames)

        if sampwidth == 1:
            audio = np.frombuffer(raw, dtype=np.uint8).astype(np.float32)
            audio = (audio - 128.0) / 128.0
        elif sampwidth == 2:
            audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
            audio = audio / 32768.0
        elif sampwidth == 4:
            audio = np.frombuffer(raw, dtype=np.int32).astype(np.float32)
            audio = audio / 2147483648.0
        else:
            raise ValueError(f"Unsupported WAV sample width: {sampwidth}")

        if n_channels == 2:
            audio = audio.reshape(-1, 2).mean(axis=1)
        elif n_channels != 1:
            raise ValueError(f"Unsupported channel count: {n_channels}")

        if framerate != TARGET_SAMPLE_RATE:
            old_len = audio.shape[0]
            new_len = int(round(old_len * TARGET_SAMPLE_RATE / framerate))
            if new_len <= 0:
                raise ValueError("Empty audio after resampling.")
            x_old = np.linspace(0.0, 1.0, old_len, endpoint=False)
            x_new = np.linspace(0.0, 1.0, new_len, endpoint=False)
            audio = np.interp(x_new, x_old, audio).astype(np.float32)

        return audio

    def transcribe(self, audio_path: str) -> dict:
        if not audio_path or not os.path.exists(audio_path):
            return {"status": "error", "text": "",
                    "message": f"Audio file not found: {audio_path}"}
        try:
            model = self._get_whisper()

            if audio_path.lower().endswith(".wav"):
                audio_array = self._decode_wav_to_array(audio_path)
                segments, _info = model.transcribe(
                    audio_array,
                    language="en",
                    vad_filter=True,
                    vad_parameters={"min_silence_duration_ms": 500},
                    initial_prompt=self._menu_prompt,
                    beam_size=5,
                    condition_on_previous_text=False,
                )
            else:
                # Fallback path: faster-whisper opens the file itself (uses av).
                segments, _info = model.transcribe(
                    audio_path,
                    language="en",
                    vad_filter=True,
                    vad_parameters={"min_silence_duration_ms": 500},
                    initial_prompt=self._menu_prompt,
                    beam_size=5,
                    condition_on_previous_text=False,
                )

            text = " ".join(seg.text.strip() for seg in segments).strip()
            if not text:
                return {"status": "error", "text": "",
                        "message": "I couldn't hear anything. Please try again."}
            if text[0].isalpha():
                text = text[0].upper() + text[1:]
            return {"status": "success", "text": text}
        except Exception as e:
            return {"status": "error", "text": "",
                    "message": f"Speech-to-text failed: {e}"}

    def warmup(self) -> dict:
        """Force-load the STT model.

        Call once at server startup so the first transcription does not
        block on model load. Also turns a silent 'model not cached'
        failure at demo time into a loud startup warning."""
        try:
            self._get_whisper()
            return {"status": "success"}
        except Exception as e:
            return {"status": "error",
                    "message": f"STT warmup failed: {e}"}


    # ---------- TTS ----------
    @staticmethod
    def _clean_for_tts(text: str) -> str:
        t = text or ""

        def _price_repl(m):
            num = m.group(1).replace(",", "")
            if num.endswith(".00"):
                num = num[:-3]
            unit = "peso" if num == "1" else "pesos"
            return f"{num} {unit}"

        # "₱220.00" -> "220 pesos", "₱1.00" -> "1 peso"
        t = re.sub(r"₱\s*([\d,]+(?:\.\d+)?)", _price_repl, t)
        # strip markdown emphasis markers
        t = re.sub(r"[*_`#>]+", "", t)
        # collapse whitespace
        t = re.sub(r"\s+", " ", t).strip()
        return t

    def _new_tts_engine(self):
        import pyttsx3
        engine = pyttsx3.init()
        engine.setProperty("rate", self._tts_rate)
        if self._tts_voice:
            for v in engine.getProperty("voices") or []:
                if self._tts_voice.lower() in (v.name or "").lower():
                    engine.setProperty("voice", v.id)
                    break
        return engine

    def speak(self, text: str) -> dict:
        text = self._clean_for_tts(text)
        if not text:
            return {"status": "error", "message": "No text to speak."}
        try:
            engine = self._new_tts_engine()
            engine.say(text)
            engine.runAndWait()
            engine.stop()
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": f"Text-to-speech failed: {e}"}

    def synthesize(self, text: str, output_path: str) -> dict:
        text = self._clean_for_tts(text)
        if not text:
            return {"status": "error", "message": "No text to synthesize."}
        try:
            out_dir = os.path.dirname(os.path.abspath(output_path))
            if out_dir:
                os.makedirs(out_dir, exist_ok=True)
            engine = self._new_tts_engine()
            engine.save_to_file(text, output_path)
            engine.runAndWait()
            engine.stop()
            if not os.path.exists(output_path):
                return {"status": "error",
                        "message": "TTS produced no file."}
            return {"status": "success", "path": output_path}
        except Exception as e:
            return {"status": "error", "message": f"Text-to-speech failed: {e}"}


# Module-level singleton for Flask (Phase 5 will use this).
_ENGINE: Optional[SpeechEngine] = None


def get_engine() -> SpeechEngine:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = SpeechEngine()
    return _ENGINE