import json

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
