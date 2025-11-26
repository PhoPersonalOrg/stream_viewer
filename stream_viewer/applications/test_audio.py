#!/usr/bin/env python
"""
Simple audio test script to verify sounddevice is working.
Outputs a constant tone at 440 Hz for 3 seconds.

Usage:
    python -m stream_viewer.applications.test_audio
"""

import sys
import time
import numpy as np

def test_constant_tone():
    """Test audio output with a simple constant sine wave."""
    print("=" * 50)
    print("Audio Device Test")
    print("=" * 50)
    
    try:
        import sounddevice as sd
        print(f"✓ sounddevice version: {sd.__version__}")
    except ImportError as e:
        print(f"✗ Failed to import sounddevice: {e}")
        print("  Install with: pip install sounddevice")
        return False
    
    # Show available devices
    print("\nAvailable audio devices:")
    print("-" * 50)
    try:
        devices = sd.query_devices()
        print(devices)
        print("-" * 50)
        
        default_output = sd.query_devices(kind='output')
        print(f"\nDefault output device: {default_output['name']}")
        print(f"  Sample rate: {default_output['default_samplerate']} Hz")
        print(f"  Output channels: {default_output['max_output_channels']}")
    except Exception as e:
        print(f"✗ Failed to query devices: {e}")
        return False
    
    # Audio parameters
    sample_rate = 44100
    frequency = 440.0  # A4 note
    duration = 3.0  # seconds
    volume = 0.3
    
    print(f"\n{'=' * 50}")
    print(f"Playing test tone:")
    print(f"  Frequency: {frequency} Hz (A4)")
    print(f"  Duration: {duration} seconds")
    print(f"  Volume: {int(volume * 100)}%")
    print(f"  Sample rate: {sample_rate} Hz")
    print(f"{'=' * 50}")
    
    # Generate the tone
    t = np.linspace(0, duration, int(sample_rate * duration), dtype=np.float32)
    tone = (volume * np.sin(2 * np.pi * frequency * t)).astype(np.float32)
    
    # Apply fade in/out to prevent clicks
    fade_samples = int(sample_rate * 0.05)  # 50ms fade
    fade_in = np.linspace(0, 1, fade_samples, dtype=np.float32)
    fade_out = np.linspace(1, 0, fade_samples, dtype=np.float32)
    tone[:fade_samples] *= fade_in
    tone[-fade_samples:] *= fade_out
    
    print("\n▶ Playing now... (you should hear a tone)")
    
    try:
        sd.play(tone, sample_rate, blocking=True)
        print("✓ Playback completed successfully!")
        return True
    except Exception as e:
        print(f"✗ Playback failed: {e}")
        return False


def test_streaming_tone():
    """Test streaming audio output (like SonifyAudio uses)."""
    print(f"\n{'=' * 50}")
    print("Testing streaming audio (callback-based)")
    print(f"{'=' * 50}")
    
    try:
        import sounddevice as sd
    except ImportError:
        print("sounddevice not available")
        return False
    
    sample_rate = 44100
    frequency = 440.0
    duration = 3.0
    volume = 0.3
    
    # Shared state
    phase = [0.0]
    
    def audio_callback(outdata, frames, time_info, status):
        if status:
            print(f"  Status: {status}")
        
        t = np.arange(frames) / sample_rate
        # Generate sine wave with continuous phase
        signal = volume * np.sin(2 * np.pi * frequency * t + phase[0])
        outdata[:, 0] = signal.astype(np.float32)
        
        # Update phase for continuity
        phase[0] += 2 * np.pi * frequency * frames / sample_rate
        phase[0] %= 2 * np.pi
    
    print(f"  Using callback-based streaming (like SonifyAudio)")
    print(f"  Duration: {duration} seconds")
    print("\n▶ Playing now...")
    
    try:
        with sd.OutputStream(
            samplerate=sample_rate,
            channels=1,
            dtype='float32',
            callback=audio_callback
        ) as stream:
            time.sleep(duration)
        print("✓ Streaming playback completed!")
        return True
    except Exception as e:
        print(f"✗ Streaming playback failed: {e}")
        return False


def test_multiple_frequencies():
    """Test multiple frequencies like polyphonic mode."""
    print(f"\n{'=' * 50}")
    print("Testing polyphonic audio (multiple frequencies)")
    print(f"{'=' * 50}")
    
    try:
        import sounddevice as sd
    except ImportError:
        print("sounddevice not available")
        return False
    
    sample_rate = 44100
    frequencies = [261.63, 329.63, 392.00]  # C4, E4, G4 (C major chord)
    duration = 3.0
    volume = 0.2
    
    # Shared state
    phases = [0.0] * len(frequencies)
    
    def audio_callback(outdata, frames, time_info, status):
        if status:
            print(f"  Status: {status}")
        
        t = np.arange(frames) / sample_rate
        mixed = np.zeros(frames, dtype=np.float32)
        
        for i, freq in enumerate(frequencies):
            signal = np.sin(2 * np.pi * freq * t + phases[i])
            mixed += signal
            phases[i] += 2 * np.pi * freq * frames / sample_rate
            phases[i] %= 2 * np.pi
        
        # Normalize and apply volume
        mixed = mixed / len(frequencies) * volume
        outdata[:, 0] = mixed.astype(np.float32)
    
    print(f"  Playing C major chord: C4, E4, G4")
    print(f"  Frequencies: {frequencies} Hz")
    print(f"  Duration: {duration} seconds")
    print("\n▶ Playing now...")
    
    try:
        with sd.OutputStream(
            samplerate=sample_rate,
            channels=1,
            dtype='float32',
            callback=audio_callback
        ) as stream:
            time.sleep(duration)
        print("✓ Polyphonic playback completed!")
        return True
    except Exception as e:
        print(f"✗ Polyphonic playback failed: {e}")
        return False


def main():
    print("\n" + "=" * 50)
    print("  STREAM VIEWER AUDIO TEST")
    print("=" * 50)
    print("\nThis script tests if your audio output is working.")
    print("You should hear tones during each test.\n")
    
    results = []
    
    # Test 1: Simple tone
    results.append(("Simple tone (blocking)", test_constant_tone()))
    
    input("\nPress Enter to continue to streaming test...")
    
    # Test 2: Streaming (callback-based, like SonifyAudio uses)
    results.append(("Streaming tone (callback)", test_streaming_tone()))
    
    input("\nPress Enter to continue to polyphonic test...")
    
    # Test 3: Multiple frequencies
    results.append(("Polyphonic (chord)", test_multiple_frequencies()))
    
    # Summary
    print(f"\n{'=' * 50}")
    print("TEST SUMMARY")
    print(f"{'=' * 50}")
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status}: {name}")
    
    all_passed = all(r[1] for r in results)
    
    if all_passed:
        print(f"\n✓ All tests passed! Audio should work with SonifyAudio.")
        print("\nIf SonifyAudio still doesn't produce sound, the issue may be:")
        print("  - No LSL stream connected")
        print("  - Audio is muted in the app (check volume slider)")
        print("  - The EEG signal values are too small")
    else:
        print(f"\n✗ Some tests failed. Check your audio device configuration.")
        print("\nTroubleshooting tips:")
        print("  - Check system volume is not muted")
        print("  - Try a different audio output device")
        print("  - On Windows, check audio device in Sound Settings")
        print("  - On Linux, check PulseAudio/ALSA configuration")
    
    return 0 if all_passed else 1


if __name__ == '__main__':
    sys.exit(main())

