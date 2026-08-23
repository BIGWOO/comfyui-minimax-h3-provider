from pathlib import Path

from tools.download_models import _safe_file_size, progress_payload, transferred_bytes


def _model(*, relative_path: str = "pack/model.bin", repo_path: str = "pack/model.bin", size: int = 8) -> dict:
    return {
        "relative_path": relative_path,
        "repo_path": repo_path,
        "size": size,
        "sha256": "expected",
    }


def test_same_size_unverified_target_is_not_complete(tmp_path: Path):
    model = _model()
    target = tmp_path / model["relative_path"]
    target.parent.mkdir(parents=True)
    target.write_bytes(b"invalid!")

    assert transferred_bytes(tmp_path, [model], set()) == 0
    assert transferred_bytes(tmp_path, [model], {model["relative_path"]}) == model["size"]


def test_progress_counts_only_selected_model_partials(tmp_path: Path):
    model = _model(size=10)
    selected_partial = tmp_path / ".cache/huggingface/download/pack/model.bin.etag.1234.incomplete"
    selected_partial.parent.mkdir(parents=True)
    selected_partial.write_bytes(b"123")
    unrelated_partial = tmp_path / ".cache/huggingface/download/other/model.bin.etag.incomplete"
    unrelated_partial.parent.mkdir(parents=True)
    unrelated_partial.write_bytes(b"1234567890")

    assert transferred_bytes(tmp_path, [model], set()) == 3


def test_progress_uses_largest_concurrent_partial(tmp_path: Path):
    model = _model(size=10)
    partial_dir = tmp_path / ".cache/huggingface/download/pack"
    partial_dir.mkdir(parents=True)
    (partial_dir / "model.bin.etag.first.incomplete").write_bytes(b"123")
    (partial_dir / "model.bin.etag.second.incomplete").write_bytes(b"12345")

    assert transferred_bytes(tmp_path, [model], set()) == 5


def test_safe_file_size_tolerates_disappearing_file(tmp_path: Path):
    assert _safe_file_size(tmp_path / "gone.incomplete") == 0


def test_completed_model_counts_toward_aggregate_progress(tmp_path: Path):
    model = _model(size=10)
    completed = {model["relative_path"]}

    total_progress = transferred_bytes(tmp_path, [model], completed, set())

    assert total_progress == 10


def test_aggregate_progress_omits_unreliable_network_telemetry():
    payload = progress_payload(5, 10, 2.4)

    assert payload["percent"] == 50.0
    assert payload["elapsed_seconds"] == 2
    assert "speed_mbps" not in payload
    assert "eta_seconds" not in payload
