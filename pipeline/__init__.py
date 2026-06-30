"""Pipeline helpers for the evaluate_agent Airflow DAG."""

__all__ = [
    "build_run_config",
    "prepare_run_dir",
    "run_agent_batch",
    "run_swebench_eval",
    "collect_metrics",
    "write_metrics",
    "write_manifest",
    "log_mlflow_run",
]


def __getattr__(name: str):
    if name in __all__:
        from pipeline import run as run_module

        return getattr(run_module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
