def test_health_checks_database(api):
    response = api.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_openapi_document_is_served(api):
    response = api.get("/openapi.json")

    assert response.status_code == 200
    assert response.json()["info"]["title"] == "FlowDeck API"
