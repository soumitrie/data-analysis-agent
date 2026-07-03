def test_package_importable():
    from config.settings import get_settings  # noqa: F401
    from api._common import ok               # noqa: F401
    from db.models import Base               # noqa: F401
    from db.models import AnalysisRun        # noqa: F401


def test_app_imports_and_boots():
    """The run path (`python -m src` → api:app) must import cleanly."""
    import api
    assert api.app is not None


def test_graph_compiles():
    from graph.agent import agentic_ai
    assert agentic_ai is not None


def test_analysis_modules_importable():
    from analysis import store, profiling, columns, figures, housestyle  # noqa: F401
