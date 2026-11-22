from app.workers.gem_build_qa_worker import _sheet_retry_status, _sheet_sync_status


def test_partial_sheet_write_is_retried_even_if_another_tab_succeeded():
    status = _sheet_sync_status(["written", "write_failed"])
    assert status == "write_failed"
    assert _sheet_retry_status(status, 1) == "processing"


def test_sheet_write_exhaustion_is_terminal_and_other_states_complete():
    assert _sheet_retry_status("write_failed", 5) == "failed"
    assert _sheet_retry_status(_sheet_sync_status(["already_written", "disabled"]), 1) == "completed"
