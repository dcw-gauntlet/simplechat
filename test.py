from main import app
from fastapi.testclient import TestClient

client = TestClient(transport=app)  # or client = TestClient(backend=app)

def test_pass():
    assert True