def test_lists_runs_newest_first(api, seeded):
    body = api.get("/runs").json()

    assert [r["id"] for r in body] == [seeded["run2"], seeded["run1"]]
    assert body[0]["status"] == "partial"
    assert body[0]["products_succeeded"] == 1


def test_paginates_runs(api, seeded):
    body = api.get("/runs", params={"limit": 1, "offset": 1}).json()

    assert [r["id"] for r in body] == [seeded["run1"]]


def test_run_detail_includes_failure_reasons(api, seeded):
    body = api.get(f"/runs/{seeded['run2']}").json()

    assert body["trigger"] == "schedule"
    assert [(r["source_product_id"], r["status"], r["error_message"]) for r in body["results"]] == [
        ("111", "ok", None),
        ("222", "http_error", "HTTP 500"),
    ]


def test_unknown_run_is_404(api, seeded):
    assert api.get("/runs/99999").status_code == 404


def test_run_detail_includes_product_names(api, seeded):
    body = api.get(f"/runs/{seeded['run2']}").json()

    assert [r["product_name"] for r in body["results"]] == ["상품 A", "상품 B"]
