import os
from unittest.mock import patch

os.environ["AWS_REGION"] = "us-east-1"
os.environ["AWS_SQS_URL"] = "dummy"
os.environ["AWS_DYNAMODB_TABLE"] = "dummy"

with patch("threading.Thread.start"):
    from app import app


def test_health():
    client = app.test_client()
    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}
