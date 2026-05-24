import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from providers.gcp.gcs_reader_mock import GCSReaderMock
from providers.azure.blob_reader_mock import BlobReaderMock

app = FastAPI(title="Nano-IaaS Web")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/list/{provider}")
def list_resources(provider: str):
    try:
        if provider == "gcp":
            p = GCSReaderMock()
            p.authenticate({})
        elif provider == "azure":
            p = BlobReaderMock()
            p.authenticate({})
        else:
            return {"error": "Provider não encontrado"}

        resources = list(p.list_resources())
        return {"provider": provider, "resources": resources}
    except Exception as e:
        return {"error": str(e)}
