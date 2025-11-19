#!/usr/bin/env python3
"""Speaker enrollment CLI tool for AR-SmartAssistant.

This tool guides users through recording voice samples for speaker identification.
It captures multiple phrases and creates a speaker profile in the database.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import sounddevice as sd

from ..config import load_config
from ..database.repository import BrainDatabase
from ..logging_utils import log_event


class SpeakerEnrollment:
    """Interactive speaker enrollment wizard."""

    def __init__(self, config_path: str = "config.yaml") -> None:
        self.config = load_config(config_path)
        self.db = BrainDatabase(
            brain_db_path=str(self.config.storage.brain_main_db),
            metrics_db_path=str(self.config.storage.system_metrics_db),
        )
        self.sample_rate = self.config.audio.capture.sample_rate_hz
        self.required_phrases = self.config.audio.speaker_id.required_phrases
        self.min_duration = self.config.audio.speaker_id.min_duration_per_phrase_sec

        self.embeddings: list[np.ndarray] = []

    def print_banner(self) -> None:
        """Print enrollment wizard banner."""
        print("\n" + "=" * 60)
        print("  AR-SmartAssistant - Speaker Enrollment Wizard")
        print("=" * 60)
        print()
        print("This will create a voice profile for speaker identification.")
        print(f"You'll need to record {self.required_phrases} phrases,")
        print(f"each at least {self.min_duration:.0f} seconds long.")
        print()

    def list_audio_devices(self) -> None:
        """List available audio input devices."""
        print("Available audio input devices:")
        print("-" * 60)

        devices = []
        for idx, dev in enumerate(sd.query_devices()):
            if dev['max_input_channels'] > 0:
                devices.append({
                    'index': idx,
                    'name': dev['name'],
                    'channels': dev['max_input_channels'],
                    'sample_rate': dev['default_samplerate'],
                })

        if not devices:
            print("ERROR: No audio input devices found!")
            sys.exit(1)

        for dev in devices:
            marker = " (default)" if dev['index'] == sd.default.device[0] else ""
            print(f"[{dev['index']}] {dev['name']}{marker}")
            print(f"    {dev['channels']} channels @ {dev['sample_rate']:.0f} Hz")
            print()

    def select_device(self) -> int | None:
        """Prompt user to select audio device."""
        default_device = sd.default.device[0]

        print(f"Default device: {default_device}")
        response = input(f"Press Enter to use default, or enter device number: ").strip()

        if not response:
            return None  # Use default

        try:
            device_idx = int(response)
            # Verify device exists
            sd.query_devices(device_idx)
            return device_idx
        except (ValueError, sd.PortAudioError):
            print("Invalid device number! Using default.")
            return None

    def record_phrase(self, phrase_num: int) -> np.ndarray:
        """Record a single phrase from the user."""
        print(f"\nPhrase {phrase_num}/{self.required_phrases}")
        print("-" * 60)
        print("Please read the following phrase out loud:")
        print()

        # Sample phrases for enrollment
        phrases = [
            "The quick brown fox jumps over the lazy dog.",
            "She sells seashells by the seashore.",
            "How much wood would a woodchuck chuck if a woodchuck could chuck wood?",
            "Peter Piper picked a peck of pickled peppers.",
            "I scream, you scream, we all scream for ice cream.",
            "Around the rugged rocks the ragged rascal ran.",
            "Betty Botter bought some butter but she said the butter's bitter.",
            "Fuzzy Wuzzy was a bear, Fuzzy Wuzzy had no hair.",
        ]

        phrase_text = phrases[(phrase_num - 1) % len(phrases)]
        print(f'  "{phrase_text}"')
        print()

        input(f"Press Enter when ready to record ({self.min_duration:.0f} seconds)...")

        print("Recording... (speak now!)")

        # Record audio
        duration = int(self.min_duration) + 1  # Add buffer
        recording = sd.rec(
            int(duration * self.sample_rate),
            samplerate=self.sample_rate,
            channels=1,
            dtype='float32',
        )
        sd.wait()

        print("Recording complete!")

        # Playback for verification
        response = input("Play back recording? (y/n): ").strip().lower()
        if response == 'y':
            print("Playing...")
            sd.play(recording, self.sample_rate)
            sd.wait()

        # Ask to accept
        response = input("Accept this recording? (y/n): ").strip().lower()
        if response != 'y':
            print("Discarding... Let's try again.")
            return self.record_phrase(phrase_num)

        return recording.flatten()

    def compute_embedding(self, audio: np.ndarray) -> np.ndarray:
        """Compute speaker embedding from audio.

        For the POC, we'll use a simplified embedding based on spectral features.
        In production, this would use Resemblyzer or a similar model.
        """
        # Simplified embedding: extract spectral features
        # In production, replace with actual speaker embedding model

        # Compute basic features
        mean_val = float(np.mean(audio))
        std_val = float(np.std(audio))
        max_val = float(np.max(np.abs(audio)))
        energy = float(np.sum(audio ** 2) / len(audio))

        # Compute spectral centroid (simplified)
        fft = np.fft.rfft(audio)
        magnitude = np.abs(fft)
        frequencies = np.fft.rfftfreq(len(audio), 1/self.sample_rate)
        spectral_centroid = float(np.sum(frequencies * magnitude) / np.sum(magnitude)) if np.sum(magnitude) > 0 else 0

        # Create a simple embedding vector
        # In production, this would be a 256-dim Resemblyzer embedding
        embedding = np.array([
            mean_val,
            std_val,
            max_val,
            energy,
            spectral_centroid,
        ], dtype=np.float32)

        # Normalize
        embedding = embedding / (np.linalg.norm(embedding) + 1e-8)

        return embedding

    def run(self) -> None:
        """Run the enrollment wizard."""
        self.print_banner()

        # Get speaker name
        print("What should we call this speaker?")
        speaker_name = input("Name (default: 'Self'): ").strip()
        if not speaker_name:
            speaker_name = "Self"

        print(f"\nEnrolling speaker: {speaker_name}")
        print()

        # List and select audio device
        self.list_audio_devices()
        device_idx = self.select_device()

        # Set device
        if device_idx is not None:
            sd.default.device = (device_idx, sd.default.device[1])

        print(f"\nUsing device: {sd.query_devices(device_idx)['name']}")

        # Record phrases
        recordings = []
        for i in range(1, self.required_phrases + 1):
            audio = self.record_phrase(i)
            recordings.append(audio)

            # Compute embedding
            embedding = self.compute_embedding(audio)
            self.embeddings.append(embedding)

        # Compute average embedding
        avg_embedding = np.mean(self.embeddings, axis=0)

        # Compute quality metrics
        std_dev = np.std([
            np.linalg.norm(emb - avg_embedding)
            for emb in self.embeddings
        ])

        max_allowed_std = self.config.audio.speaker_id.max_embedding_std_dev

        quality = "Good" if std_dev < max_allowed_std else "Fair"

        print()
        print("=" * 60)
        print("Enrollment Summary")
        print("=" * 60)
        print(f"Speaker Name: {speaker_name}")
        print(f"Phrases Recorded: {len(recordings)}")
        print(f"Embedding Consistency: {quality} (std: {std_dev:.4f})")

        if std_dev >= max_allowed_std:
            print()
            print("WARNING: Embedding consistency is below recommended threshold.")
            print("Consider re-enrolling in a quieter environment.")

        print()

        # Save to database
        response = input("Save this speaker profile? (y/n): ").strip().lower()

        if response != 'y':
            print("Enrollment cancelled.")
            return

        # Store in database
        from ..database.repository import SpeakerProfileRecord

        profile = SpeakerProfileRecord(
            name=speaker_name,
            embedding=avg_embedding.tobytes(),
            enrollment_quality=float(quality_score := 1.0 - min(std_dev / max_allowed_std, 1.0)),
            sample_count=len(recordings),
        )

        profile_id = self.db.create_speaker_profile(profile)

        # Also create a Person entry
        from ..database.repository import PersonRecord

        person = PersonRecord(
            display_name=speaker_name,
            primary_speaker_profile_id=profile_id,
            voice_embedding=avg_embedding.tobytes(),
            relationship_tags=["self"] if speaker_name.lower() == "self" else [],
        )

        person_id = self.db.create_person(person)

        print()
        print("=" * 60)
        print(f"✓ Speaker profile saved!")
        print(f"  Profile ID: {profile_id}")
        print(f"  Person ID: {person_id}")
        print(f"  Quality Score: {quality_score:.2%}")
        print("=" * 60)
        print()

        log_event("speaker_enrolled", {
            "speaker_name": speaker_name,
            "profile_id": profile_id,
            "quality_score": quality_score,
            "std_dev": std_dev,
        })


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Speaker Enrollment Tool for AR-SmartAssistant"
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config.yaml",
        help="Path to configuration file",
    )

    args = parser.parse_args()

    try:
        enrollment = SpeakerEnrollment(config_path=args.config)
        enrollment.run()
    except KeyboardInterrupt:
        print("\n\nEnrollment cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\nError during enrollment: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
