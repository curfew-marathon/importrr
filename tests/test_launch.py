from unittest.mock import MagicMock, patch

from importrr import metrics
from src.launch import ImportrrScheduler, main_process


def _job_runs(outcome):
    return metrics.JOB_RUNS_TOTAL.labels(outcome=outcome)._value.get()


@patch("src.launch.main_process", return_value=0)
def test_run_import_job_records_success(mock_main_process):
    before = _job_runs("success")
    before_ts = metrics.LAST_SUCCESS_TIMESTAMP._value.get()

    ImportrrScheduler().run_import_job()

    mock_main_process.assert_called_once()
    assert _job_runs("success") == before + 1
    assert metrics.LAST_SUCCESS_TIMESTAMP._value.get() > before_ts


@patch("src.launch.main_process", return_value=2)
def test_run_import_job_records_partial(mock_main_process):
    before = _job_runs("partial")
    before_ts = metrics.LAST_SUCCESS_TIMESTAMP._value.get()

    ImportrrScheduler().run_import_job()

    assert _job_runs("partial") == before + 1
    # A partial run must not advance the last-clean-success timestamp.
    assert metrics.LAST_SUCCESS_TIMESTAMP._value.get() == before_ts


@patch("src.launch.main_process", side_effect=RuntimeError("boom"))
def test_run_import_job_records_error(mock_main_process):
    before = _job_runs("error")

    # run_import_job swallows the exception so the scheduler keeps running.
    ImportrrScheduler().run_import_job()

    assert _job_runs("error") == before + 1


@patch("src.launch.Sort")
@patch("src.launch.Config")
def test_main_process_counts_failed_sections(mock_config, mock_sort):
    mock_config.return_value.get_data.return_value = [
        {"album": "/a/home", "archive": "/x/home", "import": ["in"], "section": "home"},
        {"album": "/a/work", "archive": "/x/work", "import": ["in"], "section": "work"},
    ]
    # First section blows up in launch(), second succeeds.
    good = MagicMock()
    bad = MagicMock()
    bad.launch.side_effect = OSError("nope")
    mock_sort.side_effect = [bad, good]

    before = metrics.SECTION_FAILURES_TOTAL.labels(section="home")._value.get()

    failed = main_process()

    assert failed == 1
    assert (
        metrics.SECTION_FAILURES_TOTAL.labels(section="home")._value.get() == before + 1
    )
    good.launch.assert_called_once_with("in")
