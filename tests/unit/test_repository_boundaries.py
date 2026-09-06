from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


spec = spec_from_file_location("check_repo", Path(__file__).resolve().parents[2] / "scripts/check_repo.py")
checks = module_from_spec(spec)
spec.loader.exec_module(checks)


def test_core_rejects_absolute_and_relative_cli_dependencies(tmp_path):
    core = tmp_path / "src/mailops/core"
    core.mkdir(parents=True)
    (core / "example.py").write_text("from mailops.cli import runtime\nfrom ..cli import main\n")
    errors = checks.check_imports(tmp_path)
    assert len(errors) == 2
    assert all("core cannot import cli" in error for error in errors)


def test_review_can_compose_provider_and_index_without_cli(tmp_path):
    review = tmp_path / "src/mailops/review"
    review.mkdir(parents=True)
    (review / "example.py").write_text("from ..adapters.proton_bridge import adapter\nfrom mailops.index import db\n")
    assert checks.check_imports(tmp_path) == []
