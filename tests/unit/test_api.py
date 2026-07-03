"""API contract tests that require no LLM key (graph not invoked)."""


def test_health(api_client):
    r = api_client.get("/health")
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "ok"


def test_upload_preview_no_llm(api_client, sample_csv_path):
    with open(sample_csv_path, "rb") as fh:
        r = api_client.post(
            "/api/datasets",
            files={"file": ("transactions_sample.csv", fh, "text/csv")},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["error"] is None
    data = body["data"]
    assert data["dataset_id"]
    assert data["row_count"] > 5000
    amount_col = next(c for c in data["columns"] if c["name"] == "amount")
    assert amount_col["dtype"] == "float64"
    date_col = next(c for c in data["columns"] if c["name"] == "txn_date")
    assert date_col["dtype"] == "string"


def test_upload_unparseable_rejected(api_client):
    r = api_client.post(
        "/api/datasets",
        files={"file": ("bad.csv", b"\x00\x01\x02\xff\xfe", "text/csv")},
    )
    assert r.status_code in (400,)
    body = r.json()
    assert body["data"] is None
    assert body["error"]["code"]


def test_analyze_unknown_dataset_404(api_client):
    r = api_client.post("/api/datasets/nope/analyze")
    assert r.status_code == 404
    assert r.json()["error"]["code"]


def test_upload_missing_file_is_422(api_client):
    r = api_client.post("/api/datasets")
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"
