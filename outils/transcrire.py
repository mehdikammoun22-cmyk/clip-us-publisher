"""Transcrit une vidéo avec faster-whisper : transcription.json (mots horodatés) + transcription.txt lisible."""
import json, subprocess, sys, time
from pathlib import Path
import numpy as np
from faster_whisper import WhisperModel

FFMPEG = r"C:\Projets\Outils\manim-venv\Scripts\ffmpeg.exe"
video, sortie = Path(sys.argv[1]), Path(sys.argv[2])
sortie.mkdir(parents=True, exist_ok=True)
t0 = time.time()
# PyAV (utilisé par faster-whisper pour lire les fichiers) est incompatible ici : ffmpeg décode le son en PCM 16 kHz mono.
pcm = subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-i", str(video), "-vn", "-ac", "1", "-ar", "16000",
                      "-f", "s16le", "-"], capture_output=True, check=True).stdout
audio = np.frombuffer(pcm, np.int16).astype(np.float32) / 32768.0
model = WhisperModel("small", device="cpu", compute_type="int8")
segments, info = model.transcribe(audio, language="fr", word_timestamps=True, vad_filter=True)

def hms(s):
    return f"{int(s//3600):02d}:{int(s%3600//60):02d}:{s%60:06.3f}"

data, lignes = [], []
for seg in segments:
    data.append({"start": seg.start, "end": seg.end, "text": seg.text.strip(),
                 "words": [{"start": w.start, "end": w.end, "word": w.word} for w in seg.words or []]})
    lignes.append(f"[{hms(seg.start)} -> {hms(seg.end)}] {seg.text.strip()}")
    print(f"{seg.end:7.1f}/{info.duration:.0f}s", flush=True)

(sortie / "transcription.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
(sortie / "transcription.txt").write_text("\n".join(lignes), encoding="utf-8")
print(f"OK {len(data)} segments en {time.time()-t0:.0f}s", flush=True)
