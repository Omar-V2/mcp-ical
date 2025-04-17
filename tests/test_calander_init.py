import pytest
import sys

import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from src.mcp_ical.ical import CalendarManager

def test_calendar_permission_denied(monkeypatch):
    # 模拟 _request_access 返回 False（即权限被拒绝）
    monkeypatch.setattr(CalendarManager, "_request_access", lambda self: False)

    # 捕获 subprocess.run 是否被调用
    called = {}
    def fake_run(cmd, check):
        called['run'] = cmd
        return 0
    monkeypatch.setattr("subprocess.run", fake_run)

    with pytest.raises(ValueError) as excinfo:
        CalendarManager()
    assert "Calendar access not granted" in str(excinfo.value)
    assert called['run'][0] == "open"
    assert "x-apple.systempreferences:com.apple.preference.security?Privacy_Calendars" in called['run'][1]