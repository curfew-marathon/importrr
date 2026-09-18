import signal
from unittest.mock import MagicMock, patch

import pytest

from importrr import metrics
from importrr.launch import ImportrrScheduler, main_process


def _job_runs(outcome):
    return metrics.JOB_RUNS_TOTAL.labels(outcome=outcome)._value.get()


@patch("importrr.launch.main_process", return_value=0)
def test_run_import_job_records_success(mock_main_process):
    before = _job_runs("success")
    before_ts = metrics.LAST_SUCCESS_TIMESTAMP._value.get()

    ImportrrScheduler().run_import_job()

    mock_main_process.assert_called_once()
    assert _job_runs("success") == before + 1
    assert metrics.LAST_SUCCESS_TIMESTAMP._value.get() > before_ts


@patch("importrr.launch.main_process", return_value=2)
def test_run_import_job_records_partial(mock_main_process):
    before = _job_runs("partial")
    before_ts = metrics.LAST_SUCCESS_TIMESTAMP._value.get()

    ImportrrScheduler().run_import_job()

    assert _job_runs("partial") == before + 1
    # A partial run must not advance the last-clean-success timestamp.
    assert metrics.LAST_SUCCESS_TIMESTAMP._value.get() == before_ts


@patch("importrr.launch.main_process", side_effect=RuntimeError("boom"))
def test_run_import_job_records_error(mock_main_process):
    before = _job_runs("error")

    # run_import_job swallows the exception so the scheduler keeps running.
    ImportrrScheduler().run_import_job()

    assert _job_runs("error") == before + 1


@patch("importrr.launch.Sort")
@patch("importrr.launch.Config")
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


@patch("importrr.launch.Sort")
@patch("importrr.launch.Config")
def test_main_process_all_sections_succeed(mock_config, mock_sort):
    mock_config.return_value.get_data.return_value = [
        {"album": "/a/home", "archive": "/x/home", "import": ["in"], "section": "home"},
    ]
    good = MagicMock()
    mock_sort.return_value = good

    failed = main_process()

    assert failed == 0
    good.launch.assert_called_once_with("in")


@patch("importrr.launch.Config", side_effect=RuntimeError("bad config"))
def test_main_process_reraises_fatal_error(mock_config):
    with pytest.raises(RuntimeError, match="bad config"):
        main_process()


def test_signal_handler_shuts_down_scheduler_and_exits():
    scheduler = ImportrrScheduler()
    mock_inner_scheduler = MagicMock()
    scheduler.scheduler = mock_inner_scheduler

    handler = signal.getsignal(signal.SIGTERM)
    with pytest.raises(SystemExit):
        handler(signal.SIGTERM, None)

    mock_inner_scheduler.shutdown.assert_called_once()


def test_start_registers_job_runs_once_then_starts_scheduler():
    scheduler = ImportrrScheduler()
    scheduler.scheduler = MagicMock()
    scheduler.run_import_job = MagicMock()

    scheduler.start()

    scheduler.scheduler.add_job.assert_called_once()
    kwargs = scheduler.scheduler.add_job.call_args.kwargs
    assert kwargs["func"] == scheduler.run_import_job
    assert kwargs["id"] == "import_job"
    assert kwargs["max_instances"] == 1

    # The startup run happens once, unconditionally, before the scheduler
    # takes over for future ticks.
    scheduler.run_import_job.assert_called_once()
    scheduler.scheduler.start.assert_called_once()


def test_start_exits_on_unexpected_error():
    scheduler = ImportrrScheduler()
    scheduler.scheduler = MagicMock()
    scheduler.scheduler.add_job.side_effect = RuntimeError("boom")

    with pytest.raises(SystemExit) as exc_info:
        scheduler.start()

    assert exc_info.value.code == 1


def test_start_handles_keyboard_interrupt_gracefully():
    scheduler = ImportrrScheduler()
    scheduler.scheduler = MagicMock()
    scheduler.scheduler.start.side_effect = KeyboardInterrupt()

    scheduler.start()  # must not raise or exit
