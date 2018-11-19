import pytest

from brizo.run import app

app = app


@pytest.fixture
def client():
    client = app.test_client()
    yield client

json_brizo = {
    "consumer_wallet": "",
    "algorithm_did": "algo.py",
    "asset_did": "data.txt",
    "docker_image": "python:3.6-alpine",
    "memory": 1.5,
    "cpu": 1
}
