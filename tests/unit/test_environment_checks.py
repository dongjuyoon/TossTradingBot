from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def load_script(name: str):
    path = Path(__file__).resolve().parents[2] / "scripts" / name
    spec = importlib.util.spec_from_file_location(name.removesuffix(".py"), path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_toss_schema_validation_accepts_required_contract() -> None:
    module = load_script("check_toss_api.py")
    openapi = {"paths": {path: {} for path in module.REQUIRED_PATHS}}
    asyncapi = {
        "channels": {
            "realtime-trade": {},
            "realtime-orderbook": {},
            "realtime-order": {},
        }
    }
    assert module.validate(openapi, asyncapi) == []


def test_toss_schema_validation_reports_missing_contract() -> None:
    module = load_script("check_toss_api.py")
    errors = module.validate({"paths": {}}, {"channels": {}})
    assert any("REST" in error for error in errors)
    assert any("WebSocket" in error for error in errors)
