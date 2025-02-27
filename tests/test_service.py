# Copyright 2022 MOSEC Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import random
import re
import shlex
import subprocess
import time
from threading import Thread

import httpx
import pytest

import mosec

TEST_PORT = "5000"


@pytest.fixture
def http_client():
    with httpx.Client(base_url=f"http://127.0.0.1:{TEST_PORT}") as client:
        yield client


@pytest.fixture(scope="session")
def mosec_service(request):
    name, wait = request.param
    service = subprocess.Popen(
        shlex.split(f"python -u tests/{name}.py --port {TEST_PORT}"),
    )
    time.sleep(wait)  # wait for service to start
    assert service.poll() is None, "service failed to start"
    yield service
    service.terminate()
    time.sleep(2)  # wait for service to stop


@pytest.mark.parametrize(
    "mosec_service, http_client",
    [
        pytest.param(("square_service", 2), "", id="basic"),
        pytest.param(
            ("square_service_shm", 5),
            "",
            marks=pytest.mark.arrow,
            id="shm_arrow",
        ),
    ],
    indirect=["mosec_service", "http_client"],
)
def test_square_service(mosec_service, http_client):
    resp = http_client.get("/")
    assert resp.status_code == 200
    # only check the prefix since the version from setuptools_scm may not be the
    # correct one used in `Cargo.toml`
    assert resp.headers["server"].startswith("mosec/"), f"{resp.headers['server']}"

    resp = http_client.get("/metrics")
    assert resp.status_code == 200

    resp = http_client.post("/inference", json={"msg": 2})
    assert resp.status_code == 422
    assert resp.text == "request validation error: 'x'"

    resp = http_client.post("/inference", content=b"bad-binary-request")
    assert resp.status_code == 400

    validate_square_service(http_client, 2)


@pytest.mark.parametrize(
    "mosec_service, http_client",
    [
        pytest.param(("square_service", 2), "", id="basic"),
        pytest.param(
            ("square_service_shm", 5),
            "",
            marks=pytest.mark.arrow,
            id="shm_arrow",
        ),
    ],
    indirect=["mosec_service", "http_client"],
)
def test_square_service_mp(mosec_service, http_client):
    threads = []
    for _ in range(20):
        t = Thread(
            target=validate_square_service,
            args=(http_client, random.randint(-500, 500)),
        )
        t.start()
        threads.append(t)
    for t in threads:
        t.join()
    assert_batch_larger_than_one(http_client)
    assert_empty_queue(http_client)


def validate_square_service(http_client, x):
    resp = http_client.post("/inference", json={"x": x})
    assert resp.json()["x"] == x**2


def assert_batch_larger_than_one(http_client):
    metrics = http_client.get("/metrics").content.decode()
    bs = re.findall(r"batch_size_bucket.+", metrics)
    get_bs_int = lambda x: int(x.split(" ")[-1])  # noqa
    assert get_bs_int(bs[-1]) > get_bs_int(bs[0])


def assert_empty_queue(http_client):
    metrics = http_client.get("/metrics").content.decode()
    remain = re.findall(r"mosec_service_remaining_task \d+", metrics)[0]
    assert int(remain.split(" ")[-1]) == 0
