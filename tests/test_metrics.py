from unittest.mock import patch

from importrr import metrics


def test_start_calls_start_http_server_with_port():
    with patch("importrr.metrics.start_http_server") as mock_start:
        metrics.start(9201)
    mock_start.assert_called_once_with(9201)


def test_start_swallows_port_collision():
    with (
        patch(
            "importrr.metrics.start_http_server",
            side_effect=OSError("Address already in use"),
        ),
        patch("importrr.metrics.logger") as mock_logger,
    ):
        metrics.start(9201)  # must not raise
    mock_logger.error.assert_called_once()


def test_start_swallows_non_numeric_port():
    with patch("importrr.metrics.logger") as mock_logger:
        metrics.start("abc")  # must not raise
    mock_logger.error.assert_called_once()


def test_start_swallows_none_port():
    # int(None) raises TypeError; start() must still honour its "never raises"
    # contract.
    with patch("importrr.metrics.logger") as mock_logger:
        metrics.start(None)  # must not raise
    mock_logger.error.assert_called_once()


def test_start_swallows_out_of_range_port():
    # Not mocked: an out-of-range port raises OverflowError from the real
    # socket bind inside start_http_server, not from int() itself.
    with patch("importrr.metrics.logger") as mock_logger:
        metrics.start("99999999")  # must not raise
    mock_logger.error.assert_called_once()
