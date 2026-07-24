from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from botocore.exceptions import ClientError

from providers.aws.s3_reader import S3Reader


class FakeSession:
    calls = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        FakeSession.calls.append(kwargs)

    def client(self, service_name):
        return {"service": service_name}


def test_authenticate_uses_explicit_credentials(monkeypatch):
    FakeSession.calls = []
    monkeypatch.setattr("providers.aws.s3_reader.boto3.Session", FakeSession)

    reader = S3Reader()
    ok = reader.authenticate({
        "access_key_id": "ak",
        "secret_access_key": "sk",
        "session_token": "token",
        "region_name": "us-east-1",
    })

    assert ok is True
    assert FakeSession.calls == [{
        "aws_access_key_id": "ak",
        "aws_secret_access_key": "sk",
        "aws_session_token": "token",
        "region_name": "us-east-1",
    }]
    assert reader.client == {"service": "s3"}


@pytest.mark.parametrize(
    "resource_path",
    [
        "bucket-valido/dados/",
        "gs://bucket-valido/dados/",
        "s3://ab/dados/",
        "s3://bucket..invalido/dados/",
        "s3://bucket-valido/",
        "s3://bucket-valido/segredos/",
    ],
)
def test_rejects_invalid_or_out_of_scope_paths(resource_path):
    reader = S3Reader()

    with pytest.raises(ValueError):
        reader._parse_resource_path(resource_path)


def test_accepts_only_allowed_bucket_when_allowlist_is_configured():
    reader = S3Reader(allowed_buckets=["nano-iaas-raw-dev"])

    assert reader._parse_resource_path(
        "s3://nano-iaas-raw-dev/dados/"
    ) == ("nano-iaas-raw-dev", "dados/")

    with pytest.raises(ValueError, match="Bucket S3 não autorizado"):
        reader._parse_resource_path(
            "s3://nano-iaas-archive-dev/dados/"
        )


def test_list_resources_uses_configured_allowlist_without_global_listing():
    class ClientThatMustNotBeCalled:
        def list_buckets(self):
            raise AssertionError("list_buckets não deveria ser chamado")

    reader = S3Reader(
        allowed_buckets=[
            "nano-iaas-raw-dev",
            "nano-iaas-archive-dev",
        ]
    )
    reader.client = ClientThatMustNotBeCalled()

    assert list(reader.list_resources()) == [
        {
            "name": "nano-iaas-archive-dev",
            "created": None,
            "type": "bucket",
        },
        {
            "name": "nano-iaas-raw-dev",
            "created": None,
            "type": "bucket",
        },
    ]


def test_read_lists_and_reads_only_dados_prefix():
    modified = datetime(2026, 7, 23, tzinfo=timezone.utc)

    class FakePaginator:
        def __init__(self):
            self.calls = []

        def paginate(self, **kwargs):
            self.calls.append(kwargs)
            return [{
                "Contents": [{
                    "Key": "dados/users.jsonl",
                    "LastModified": modified,
                    "Size": 12,
                }]
            }]

    class FakeBody:
        def read(self):
            return b'{"id": 1}\n'

    paginator = FakePaginator()

    class FakeClient:
        def get_paginator(self, operation):
            assert operation == "list_objects_v2"
            return paginator

        def get_object(self, **kwargs):
            assert kwargs == {
                "Bucket": "bucket-valido",
                "Key": "dados/users.jsonl",
            }
            return {"Body": FakeBody()}

    reader = S3Reader()
    reader.client = FakeClient()
    reader.data_reader = SimpleNamespace(
        infer_format=lambda key: "jsonl",
        parse_raw=lambda content, file_format: iter([{"id": 1}]),
    )

    records = list(reader.read("s3://bucket-valido/dados/"))

    assert paginator.calls == [{
        "Bucket": "bucket-valido",
        "Prefix": "dados/",
    }]
    assert records == [{
        "id": 1,
        "_source": "s3://bucket-valido/dados/users.jsonl",
        "_last_modified": modified.isoformat(),
        "_size": 12,
    }]


def test_get_metadata_sanitizes_client_error():
    sensitive = "detalhe-operacional-secreto"
    error = ClientError(
        {
            "Error": {
                "Code": "AccessDenied",
                "Message": sensitive,
            }
        },
        "HeadObject",
    )

    class FailingClient:
        def head_object(self, **_kwargs):
            raise error

    reader = S3Reader()
    reader.client = FailingClient()

    result = reader.get_metadata(
        "s3://bucket-valido/dados/users.jsonl"
    )

    assert result == {
        "error": "Falha ao consultar metadados S3"
    }
    assert sensitive not in str(result)


def test_validate_credentials_uses_aws_sts():
    calls = []

    class FakeSTS:
        def get_caller_identity(self):
            calls.append("get_caller_identity")
            return {"Account": "000000000000"}

    class FakeSession:
        def client(self, service):
            calls.append(service)
            return FakeSTS()

    reader = S3Reader()
    reader.session = FakeSession()

    assert reader.validate_credentials() is True
    assert calls == ["sts", "get_caller_identity"]
