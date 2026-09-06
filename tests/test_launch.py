from unittest.mock import patch

from importrr import metrics
from src.launch import ImportrrScheduler


def _job_runs(outcome):
    return metrics.JOB_RUNS_TOTAL.labels(outcome=outcome)._value.get()


@patch("src.launch.main_process")
def test_run_import_job_records_success(mock_main_process):
    before = _job_runs("success")
    before_ts = metrics.LAST_SUCCESS_TIMESTAMP._value.get()

    ImportrrScheduler().run_import_job()

    mock_main_process.assert_called_once()
    assert _job_runs("success") == before + 1
    assert metrics.LAST_SUCCESS_TIMESTAMP._value.get() > before_ts


@patch("src.launch.main_process", side_effect=RuntimeError("boom"))
def test_run_import_job_records_error(mock_main_process):
    before = _job_runs("error")

    # run_import_job swallows the exception so the scheduler keeps running.
    ImportrrScheduler().run_import_job()

    assert _job_runs("error") == before + 1
