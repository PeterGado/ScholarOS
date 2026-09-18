import boto3
import pytest
from moto import mock_aws

from app.storage.s3_compatible import S3CompatibleStorage

BUCKET = "scholaros-test-bucket"


@pytest.fixture()
def storage():
    with mock_aws():
        boto3.client("s3", region_name="us-east-1").create_bucket(Bucket=BUCKET)
        yield S3CompatibleStorage(bucket=BUCKET, region_name="us-east-1")


def test_save_and_read_round_trip(storage):
    reference = storage.save(b"hello world", extension="txt")
    assert storage.exists(reference)
    assert storage.read(reference) == b"hello world"


def test_save_is_content_addressed_and_idempotent(storage):
    ref1 = storage.save(b"same content")
    ref2 = storage.save(b"same content")
    assert ref1 == ref2
    assert storage.read(ref1) == b"same content"


def test_different_content_yields_different_references(storage):
    ref1 = storage.save(b"content A")
    ref2 = storage.save(b"content B")
    assert ref1 != ref2


def test_delete_removes_object(storage):
    reference = storage.save(b"to delete")
    storage.delete(reference)
    assert not storage.exists(reference)


def test_delete_is_safe_when_object_missing(storage):
    storage.delete("never-existed.txt")  # must not raise


def test_exists_is_false_for_an_unknown_reference(storage):
    assert not storage.exists("nonexistent-reference.txt")


def test_read_of_a_missing_reference_raises(storage):
    with pytest.raises(Exception):  # noqa: B017 - the real boto3 ClientError, not a domain error
        storage.read("nonexistent-reference.txt")
