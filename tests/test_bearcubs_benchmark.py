import importlib.util
import io
import sys
import types
import zipfile
from pathlib import Path

import pytest


def _load_bearcubs_module():
    benchmark_module = types.ModuleType("magentic_ui.eval.benchmark")

    class Benchmark:
        pass

    benchmark_module.Benchmark = Benchmark
    models_module = types.ModuleType("magentic_ui.eval.models")
    for name in [
        "BaseTask",
        "BaseEvalResult",
        "AllTaskTypes",
        "AllCandidateTypes",
        "AllEvalResultTypes",
    ]:
        setattr(models_module, name, object)

    sys.modules.setdefault("magentic_ui.eval.benchmark", benchmark_module)
    sys.modules.setdefault("magentic_ui.eval.models", models_module)

    module_path = (
        Path(__file__).parents[1]
        / "src"
        / "magentic_ui"
        / "eval"
        / "benchmarks"
        / "bearcubs"
        / "bearcubs.py"
    )
    spec = importlib.util.spec_from_file_location(
        "magentic_ui.eval.benchmarks.bearcubs.bearcubs", module_path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _zip_file(entries: dict[str, str]) -> zipfile.ZipFile:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zip_file:
        for name, content in entries.items():
            zip_file.writestr(name, content)
    buffer.seek(0)
    return zipfile.ZipFile(buffer, "r")


def test_bearcubs_zip_members_reject_traversal_path():
    bearcubs = _load_bearcubs_module()

    with _zip_file({"../escape.json": "{}"}) as zip_ref:
        with pytest.raises(ValueError, match="Unsafe path"):
            bearcubs._safe_zip_members(zip_ref)


def test_bearcubs_zip_members_allow_dataset_file():
    bearcubs = _load_bearcubs_module()

    with _zip_file({"BearCubs_20250310.json": "{}"}) as zip_ref:
        members = bearcubs._safe_zip_members(zip_ref)

    assert [member.filename for member in members] == ["BearCubs_20250310.json"]
