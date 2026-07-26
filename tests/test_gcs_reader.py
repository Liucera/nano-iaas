import json

import pytest
from google.api_core.exceptions import GoogleAPIError

from providers.gcp.gcs_reader import GCSReader


class FakeCredentials:
    calls = []

    @classmethod
    def from_service_account_info(cls, info):
        cls.calls.append(info)
        return {"credentials": info["client_email"]}


class FakeStorageClient:
    calls = []

    def __init__(self, project=None, credentials=None):
        FakeStorageClient.calls.append({"project": project, "credentials": credentials})


def test_authenticate_uses_service_account_json(monkeypatch):
    FakeCredentials.calls = []
    FakeStorageClient.calls = []
    monkeypatch.setattr("providers.gcp.gcs_reader.service_account.Credentials", FakeCredentials)
    monkeypatch.setattr("providers.gcp.gcs_reader.storage.Client", FakeStorageClient)
    info = {"project_id": "nano-dev", "client_email": "svc@example.com"}
    reader = GCSReader()
    ok = reader.authenticate({"service_account_json": json.dumps(info)})
    assert ok is True
    assert FakeCredentials.calls == [info]
    assert FakeStorageClient.calls == [{"project": "nano-dev", "credentials": {"credentials": "svc@example.com"}}]
    assert reader.project_id == "nano-dev"


@pytest.mark.parametrize("operation", ["list", "read", "metadata"])
def test_google_errors_never_log_or_return_sensitive_exception(operation, monkeypatch):
    from unittest.mock import Mock

    sensitive = "fictitious-private-material service-account@example.invalid"
    error = GoogleAPIError(sensitive)
    captured_logger = Mock()
    monkeypatch.setattr(
        "providers.gcp.gcs_reader.logger",
        captured_logger,
    )

    class FailingBucket:
        def get_blob(self, _name):
            raise error

    class FailingClient:
        def list_buckets(self):
            raise error

        def bucket(self, _name):
            return FailingBucket()

        def list_blobs(self, *_args, **_kwargs):
            raise error

    reader = GCSReader()
    reader.client = FailingClient()

    if operation == "list":
        with pytest.raises(GoogleAPIError):
            list(reader.list_resources())
    elif operation == "read":
        with pytest.raises(GoogleAPIError):
            list(reader.read("gs://fictitious-bucket"))
    else:
        assert reader.get_metadata("gs://fictitious-bucket/object") == {
            "error": "Falha ao obter metadados GCS"
        }

    if operation == "list":
        captured_logger.error.assert_called_once_with(
            "provider_list_failed",
            extra={
                "provider": "gcp",
                "operation": "list_resources",
            },
        )
    elif operation == "read":
        captured_logger.error.assert_called_once_with(
            "provider_read_failed",
            extra={
                "provider": "gcp",
                "operation": "read",
            },
        )
    else:
        captured_logger.error.assert_not_called()

    output = repr(captured_logger.mock_calls)
    assert sensitive not in output


def test_validate_credentials_limits_gcp_bucket_query():
    calls = []

    class FakeClient:
        def list_buckets(self, max_results):
            calls.append(max_results)
            return iter([])

    reader = GCSReader()
    reader.client = FakeClient()

    assert reader.validate_credentials() is True
    assert calls == [1]
