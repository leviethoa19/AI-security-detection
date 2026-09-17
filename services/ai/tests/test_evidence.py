from __future__ import annotations

from pathlib import Path

import numpy as np

from security_ai.evidence import RollingEvidenceRecorder, write_evidence_capture


def _frame(value: int) -> np.ndarray:  # type: ignore[type-arg]
    return np.full((24, 32, 3), value, dtype=np.uint8)


def test_rolling_buffer_keeps_pre_and_post_event_frames() -> None:
    recorder = RollingEvidenceRecorder(pre_event_ms=1_000, post_event_ms=1_000)
    for timestamp in (0, 500, 1_000, 1_500):
        recorder.push(timestamp, _frame(timestamp // 10))

    assert recorder.trigger("incident-1", 1_500)
    assert not recorder.trigger("incident-1", 1_500)
    recorder.push(2_000, _frame(200))
    recorder.push(2_500, _frame(250))

    captures = recorder.drain_completed()
    assert len(captures) == 1
    assert captures[0].complete
    assert [frame.source_time_ms for frame in captures[0].frames] == [
        500,
        1_000,
        1_500,
        2_000,
        2_500,
    ]


def test_finalize_marks_short_post_window_incomplete() -> None:
    recorder = RollingEvidenceRecorder(pre_event_ms=500, post_event_ms=1_000)
    recorder.push(0, _frame(0))
    recorder.trigger("incident-1", 0)
    recorder.push(500, _frame(50))

    captures = recorder.finalize()
    assert len(captures) == 1
    assert not captures[0].complete


def test_evidence_writer_creates_private_artifact_set(tmp_path: Path) -> None:
    recorder = RollingEvidenceRecorder(pre_event_ms=500, post_event_ms=500)
    recorder.push(0, _frame(0))
    recorder.push(500, _frame(50))
    recorder.trigger("incident-1", 500)
    recorder.push(1_000, _frame(100))
    capture = recorder.drain_completed()[0]

    artifact = write_evidence_capture(capture, output_dir=tmp_path, fps=2.0)

    assert Path(artifact.clip_path).stat().st_size > 0
    assert Path(artifact.thumbnail_path).stat().st_size > 0
    assert Path(artifact.manifest_path).stat().st_size > 0
    assert artifact.frame_count == 3
