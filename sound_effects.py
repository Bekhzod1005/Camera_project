import io
import wave
import threading
import numpy as np

try:
    import winsound
except ImportError:
    winsound = None

def synthesize_beep_pattern(frequency=800, duration=0.18, volume=0.5, count=1, pause=0.08, sample_rate=44100):
    """
    Generate an in-memory PCM 16-bit WAV audio buffer with precise volume amplitude
    and multi-beep rhythm patterns.
    """
    total_audio = []
    fade_len = int(sample_rate * 0.015)
    fade_in = np.linspace(0, 1, fade_len)
    fade_out = np.linspace(1, 0, fade_len)

    t_single = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    single_beep = np.sin(2 * np.pi * frequency * t_single) * float(volume)

    if len(single_beep) >= fade_len * 2:
        single_beep[:fade_len] *= fade_in
        single_beep[-fade_len:] *= fade_out

    pause_samples = int(sample_rate * pause)
    pause_block = np.zeros(pause_samples, dtype=np.float32)

    for i in range(count):
        total_audio.append(single_beep)
        if i < count - 1:
            total_audio.append(pause_block)

    combined = np.concatenate(total_audio)
    combined = np.clip(combined, -1.0, 1.0)
    audio_int16 = (combined * 32767).astype(np.int16)

    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio_int16.tobytes())
    return buf.getvalue()

def synthesize_success_chime(sample_rate=44100):
    """Ascending cheerful chord (C5, E5, G5) at pleasant moderate volume."""
    notes = [523.25, 659.25, 783.99]
    dur = 0.12
    t = np.linspace(0, dur, int(sample_rate * dur), endpoint=False)
    total_audio = []

    fade_len = int(sample_rate * 0.01)
    fade_in = np.linspace(0, 1, fade_len)
    fade_out = np.linspace(1, 0, fade_len)

    for freq in notes:
        audio = np.sin(2 * np.pi * freq * t) * 0.45
        audio[:fade_len] *= fade_in
        audio[-fade_len:] *= fade_out
        total_audio.append(audio)

    combined = np.concatenate(total_audio)
    audio_int16 = (combined * 32767).astype(np.int16)

    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio_int16.tobytes())
    return buf.getvalue()

# Pre-cached sound buffers for instantaneous zero-latency playback
CACHE = {
    1: synthesize_beep_pattern(frequency=650, duration=0.18, volume=0.25, count=1),
    2: synthesize_beep_pattern(frequency=780, duration=0.18, volume=0.50, count=2, pause=0.07),
    3: synthesize_beep_pattern(frequency=950, duration=0.16, volume=0.75, count=3, pause=0.06),
    4: synthesize_beep_pattern(frequency=1200, duration=0.14, volume=1.00, count=4, pause=0.05),
    "success": synthesize_success_chime()
}

def play_progressive_warning(level=1, sound_enabled=True):
    """
    Play progressively louder warning audio based on warning level.
    Level 1: 25% volume, 1 gentle chime
    Level 2: 50% volume, 2 chimes
    Level 3: 75% volume, 3 chimes
    Level 4+: 100% volume, 4 rapid urgent chimes
    """
    if not sound_enabled or not winsound:
        return

    bounded_level = max(1, min(4, level))
    wav_bytes = CACHE.get(bounded_level, CACHE[1])

    def _play():
        try:
            winsound.PlaySound(wav_bytes, winsound.SND_MEMORY)
        except Exception:
            pass

    threading.Thread(target=_play, daemon=True).start()

def play_success_sound(sound_enabled=True):
    """Play pleasant success chime asynchronously."""
    if not sound_enabled or not winsound:
        return

    wav_bytes = CACHE["success"]
    def _play():
        try:
            winsound.PlaySound(wav_bytes, winsound.SND_MEMORY)
        except Exception:
            pass

    threading.Thread(target=_play, daemon=True).start()
