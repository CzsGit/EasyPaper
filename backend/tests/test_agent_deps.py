from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api.agent_deps import require_agent_api_key


def test_require_agent_api_key_rejects_missing_header():
    app = FastAPI()

    @app.get("/protected")
    def protected(_: None = Depends(require_agent_api_key)):
        return {"ok": True}

    client = TestClient(app)
    response = client.get("/protected")

    assert response.status_code == 403
