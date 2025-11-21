# app/simulation_fullflow_v3_7.py
"""
Shim to root-level 'simulation_fullflow_v3_7.py'.
앱 레이어는 이 모듈을 임포트하면 되고, 실제 구현은 루트의 v3.7 파일이 수행합니다.
"""
import importlib

_impl = importlib.import_module("simulation_fullflow_v3_7")

SimConfig = getattr(_impl, "SimConfig")
run = getattr(_impl, "run")

__all__ = ["SimConfig", "run"]

if __name__ == "__main__":
    if hasattr(_impl, "main"):
        _impl.main()