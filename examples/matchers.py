import niquests

from niquests_mock import MockRouter


def test_richer_matchers() -> None:
    with MockRouter(base_url="https://api.example.test") as router:
        jobs = router.post(
            "/jobs",
            name="jobs.create",
            headers={"X-Trace": "trace-1"},
            params={"expand": "details"},
            json={"name": "build"},
        ).respond(status_code=201, json={"id": 1})

        response = niquests.post(
            "https://api.example.test/jobs?expand=details",
            json={"name": "build"},
            headers={"X-Trace": "trace-1"},
        )

    jobs.assert_called_once_with(
        headers={"X-Trace": "trace-1"},
        params={"expand": "details"},
        json={"name": "build"},
    )
    assert router["jobs.create"] is jobs
    assert response.status_code == 201
