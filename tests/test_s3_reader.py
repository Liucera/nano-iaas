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
