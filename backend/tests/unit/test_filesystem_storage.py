import pytest

from app.storage.filesystem import FilesystemStorage


def test_save_and_read_round_trip(tmp_path):
    storage = FilesystemStorage(tmp_path)
    reference = storage.save(b"hello world", extension="txt")
    assert storage.exists(reference)
    assert storage.read(reference) == b"hello world"


def test_save_is_content_addressed_and_idempotent(tmp_path):
    storage = FilesystemStorage(tmp_path)
    ref1 = storage.save(b"same content")
    ref2 = storage.save(b"same content")
    assert ref1 == ref2
    assert len(list(tmp_path.glob("*"))) == 1


def test_different_content_yields_different_references(tmp_path):
    storage = FilesystemStorage(tmp_path)
    ref1 = storage.save(b"content A")
    ref2 = storage.save(b"content B")
    assert ref1 != ref2


def test_delete_removes_file(tmp_path):
    storage = FilesystemStorage(tmp_path)
    reference = storage.save(b"to delete")
    storage.delete(reference)
    assert not storage.exists(reference)


def test_delete_is_safe_when_file_missing(tmp_path):
    storage = FilesystemStorage(tmp_path)
    storage.delete("never-existed.txt")  # must not raise


def test_read_rejects_path_traversal(tmp_path):
    storage = FilesystemStorage(tmp_path)
    with pytest.raises(ValueError):
        storage.read("../outside.txt")


def test_root_directory_is_created_if_missing(tmp_path):
    new_root = tmp_path / "nested" / "storage"
    FilesystemStorage(new_root)
    assert new_root.is_dir()
