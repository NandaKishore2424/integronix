"""
Tests for the shared embedding model, startup warm-up, and the order in which
the pipeline saves its results.

Three production defects sit behind this file, none visible to the rest of the
suite because every other test fakes the model and the database:

  * The Docker image could not load the model. Both nodes loaded it by hub name
    under HF_HUB_OFFLINE=1, and an offline lookup does not find a copy saved to
    a plain directory — vector search would have failed on every deploy.
  * The first request after a restart took ~55 s: model load, graph compile and
    cold pgvector indexes, all paid by whoever asked first.
  * Results were saved before they were priced. risk_scoring persists the case
    and ran before financial_calc, so every stored result had an empty
    financial summary and Case History showed no revenue.
"""
import asyncio

import numpy as np
import pytest

import services.embedding_model as em


@pytest.fixture(autouse=True)
def _fresh_model_state(monkeypatch):
    monkeypatch.setattr(em, "_model", None)
    monkeypatch.setattr(em, "_warm_up_state", None)


class _FakeModel:
    def __init__(self):
        self.encodes = 0

    def encode(self, text, normalize_embeddings=False):
        self.encodes += 1
        return np.zeros(384, dtype="float32")


class TestModelResolution:
    def test_explicit_setting_wins(self, monkeypatch, tmp_path):
        monkeypatch.setattr(em.settings, "embedding_model_path", str(tmp_path))
        assert em.resolve_model_ref() == str(tmp_path)

    def test_copy_baked_into_the_image_is_loaded_by_path(self, monkeypatch, tmp_path):
        """
        Regression: loading by NAME inside the image raised OSError with
        networking off. The baked directory must be loaded by PATH.
        """
        baked = tmp_path / em.MODEL_NAME
        baked.mkdir()
        monkeypatch.setattr(em.settings, "embedding_model_path", "")
        monkeypatch.setattr(em, "BAKED_MODEL_DIR", str(baked))
        assert em.resolve_model_ref() == str(baked)

    def test_hub_name_only_when_no_local_copy_exists(self, monkeypatch, tmp_path):
        monkeypatch.setattr(em.settings, "embedding_model_path", "")
        monkeypatch.setattr(em, "BAKED_MODEL_DIR", str(tmp_path / "absent"))
        assert em.resolve_model_ref() == em.MODEL_NAME


class TestSharedModel:
    def test_model_is_loaded_once_and_shared(self, monkeypatch):
        loads = []
        monkeypatch.setattr(em, "_load", lambda ref: loads.append(ref) or _FakeModel())
        first = em.get_embedding_model()
        second = em.get_embedding_model()
        assert first is second
        assert len(loads) == 1, "two loads means two copies of the model in memory"

    def test_icd_node_uses_the_shared_instance(self, monkeypatch):
        from agents.icd_embedding import _get_model

        monkeypatch.setattr(em, "_load", lambda ref: _FakeModel())
        assert _get_model() is em.get_embedding_model()

    def test_cpt_node_no_longer_loads_a_model_at_import(self):
        import agents.cpt_resolver as cpt

        assert not hasattr(cpt, "_embedding_model")


class TestWarmUp:
    def test_success_is_recorded(self, monkeypatch):
        monkeypatch.setattr(em, "_load", lambda ref: _FakeModel())
        state = em.run_warm_up()
        assert state["ok"] is True
        assert em.warm_up_status() == state

    def test_failure_is_recorded_not_raised(self, monkeypatch):
        def broken(ref):
            raise OSError("couldn't connect to 'https://huggingface.co'")

        monkeypatch.setattr(em, "_load", broken)
        state = em.run_warm_up()
        assert state == {"ok": False, "error_type": "OSError"}

    def test_services_warm_up_primes_both_vector_indexes(self, monkeypatch):
        import services.warmup as warmup

        calls = []

        async def fake_rpc(name, params):
            calls.append(name)
            return []

        monkeypatch.setattr(em, "_load", lambda ref: _FakeModel())
        monkeypatch.setattr(warmup, "rpc", fake_rpc)
        summary = asyncio.run(warmup.warm_up_services())

        assert summary["model_ok"] is True
        assert summary["graph_ok"] is True
        assert summary["vector_indexes_primed"] is True
        assert sorted(calls) == ["match_cpt_codes", "match_icd_codes"]

    def test_unreachable_database_does_not_stop_startup(self, monkeypatch):
        import services.warmup as warmup

        async def failing_rpc(name, params):
            raise ConnectionError("database unreachable")

        monkeypatch.setattr(em, "_load", lambda ref: _FakeModel())
        monkeypatch.setattr(warmup, "rpc", failing_rpc)
        summary = asyncio.run(warmup.warm_up_services())
        assert summary["model_ok"] is True
        assert summary["vector_indexes_primed"] is False


class TestReadinessReportsTheModel:
    def test_failed_model_makes_the_instance_not_ready(self, anon_client, fake_db, monkeypatch):
        """A healthy database is not enough: an instance that cannot embed cannot serve."""
        fake_db.on("select", [{"code": "A00"}])
        monkeypatch.setattr(em, "_warm_up_state", {"ok": False, "error_type": "OSError"})
        res = anon_client.get("/health")
        assert res.status_code == 503
        body = res.json()
        assert body["checks"]["database"]["ok"] is True
        assert body["checks"]["embedding_model"]["ok"] is False

    def test_loaded_model_and_database_are_ready(self, anon_client, fake_db, monkeypatch):
        fake_db.on("select", [{"code": "A00"}])
        monkeypatch.setattr(em, "_warm_up_state", {"ok": True, "load_ms": 200})
        res = anon_client.get("/health")
        assert res.status_code == 200
        assert res.json()["checks"]["embedding_model"]["ok"] is True

    def test_check_is_omitted_when_warm_up_never_ran(self, anon_client, fake_db):
        fake_db.on("select", [{"code": "A00"}])
        res = anon_client.get("/health")
        assert res.status_code == 200
        assert "embedding_model" not in res.json()["checks"]


class TestResultsAreSavedAfterPricing:
    def test_financials_run_before_the_node_that_persists(self):
        from agents.graph import get_compiled_graph

        edges = {(e.source, e.target) for e in get_compiled_graph().get_graph().edges}
        assert ("audit_comparison", "financial_calc") in edges
        assert ("financial_calc", "risk_scoring") in edges
        assert ("risk_scoring", "__end__") in edges
        assert ("risk_scoring", "financial_calc") not in edges

    def test_compiled_graph_is_built_once(self):
        from agents.graph import get_compiled_graph

        assert get_compiled_graph() is get_compiled_graph()
