"""AnalysisRun persistence — no LLM key required."""
import json

from sqlalchemy.orm import Session

from db.models import AnalysisRun


def test_analysis_run_roundtrip(_isolated_db):
    with Session(_isolated_db) as s:
        run = AnalysisRun(dataset_id="d1", filename="f.csv", row_count=5008, status="pending")
        s.add(run)
        s.commit()
        run_id = run.id

    with Session(_isolated_db) as s:
        fetched = s.get(AnalysisRun, run_id)
        assert fetched is not None
        assert fetched.dataset_id == "d1"
        assert fetched.row_count == 5008
        assert fetched.status == "pending"
        assert fetched.column_mapping is None


def test_analysis_run_completion_update(_isolated_db):
    with Session(_isolated_db) as s:
        run = AnalysisRun(dataset_id="d2", filename="f.csv", row_count=10, status="pending")
        s.add(run)
        s.commit()
        run_id = run.id

    mapping = {"date": "txn_date", "amount": "amount"}
    with Session(_isolated_db) as s:
        run = s.get(AnalysisRun, run_id)
        run.status = "completed"
        run.column_mapping = json.dumps(mapping)
        run.chart_specs = json.dumps([{"type": "distribution"}])
        run.prompt_tokens = 900
        run.completion_tokens = 220
        run.elapsed_ms = 4200
        s.commit()

    with Session(_isolated_db) as s:
        run = s.get(AnalysisRun, run_id)
        assert run.status == "completed"
        assert json.loads(run.column_mapping)["amount"] == "amount"
        assert run.prompt_tokens == 900
        assert run.estimated_cost_usd is None


def test_multiple_runs_share_dataset(_isolated_db):
    with Session(_isolated_db) as s:
        for _ in range(3):
            s.add(AnalysisRun(dataset_id="shared", filename="f.csv", row_count=1))
        s.commit()
        rows = s.query(AnalysisRun).filter(AnalysisRun.dataset_id == "shared").all()
    assert len(rows) == 3
    assert len({r.id for r in rows}) == 3
