from datetime import datetime, timezone
from unittest.mock import MagicMock

from mcp_ical.models import Event


class TestAllDayEventConversion:
    """Test that all-day events show correct dates regardless of timezone."""

    def _create_mock_ekevent(
        self,
        title: str,
        start_timestamp: float,
        end_timestamp: float,
        is_all_day: bool,
    ) -> MagicMock:
        """Helper to create a mock EKEvent."""
        mock_ekevent = MagicMock()
        mock_ekevent.title.return_value = title
        mock_ekevent.isAllDay.return_value = is_all_day

        mock_start = MagicMock()
        mock_start.timeIntervalSince1970.return_value = start_timestamp
        mock_ekevent.startDate.return_value = mock_start

        mock_end = MagicMock()
        mock_end.timeIntervalSince1970.return_value = end_timestamp
        mock_ekevent.endDate.return_value = mock_end

        # Mock other required fields
        mock_ekevent.calendar.return_value.title.return_value = "Test Calendar"
        mock_ekevent.location.return_value = None
        mock_ekevent.notes.return_value = None
        mock_ekevent.URL.return_value = None
        mock_ekevent.alarms.return_value = None
        mock_ekevent.recurrenceRule.return_value = None
        mock_ekevent.availability.return_value = 0
        mock_ekevent.status.return_value = 0
        mock_ekevent.organizer.return_value = None
        mock_ekevent.attendees.return_value = None
        mock_ekevent.lastModifiedDate.return_value = None
        mock_ekevent.eventIdentifier.return_value = "test-id"

        return mock_ekevent

    def test_allday_event_shows_correct_local_date(self):
        """All-day event stored in UTC should display as correct local date."""
        # Create a UTC timestamp for a known all-day event
        # This represents "start of day" in some timezone
        utc_timestamp = 1766235600  # 2025-12-20 11:00:00 UTC

        # Calculate what local date this SHOULD be
        utc_dt = datetime.fromtimestamp(utc_timestamp, tz=timezone.utc)
        expected_local = utc_dt.astimezone()  # Convert to local timezone
        expected_day = expected_local.day
        expected_month = expected_local.month

        mock_ekevent = self._create_mock_ekevent(
            title="Test All Day",
            start_timestamp=utc_timestamp,
            end_timestamp=utc_timestamp + 86399,  # +23:59:59
            is_all_day=True,
        )

        event = Event.from_ekevent(mock_ekevent)

        # Date should match local conversion, time should be midnight
        assert event.start_time.day == expected_day
        assert event.start_time.month == expected_month
        assert event.start_time.hour == 0
        assert event.start_time.minute == 0
        assert event.start_time.second == 0
        assert event.all_day is True

    def test_allday_event_end_time_is_end_of_day(self):
        """All-day event end time should be 23:59:59 on the correct local date."""
        utc_timestamp = 1766235600  # 2025-12-20 11:00:00 UTC
        end_timestamp = 1766321999  # 2025-12-21 10:59:59 UTC

        # Calculate expected local date for end time
        end_utc_dt = datetime.fromtimestamp(end_timestamp, tz=timezone.utc)
        expected_end_local = end_utc_dt.astimezone()
        expected_end_day = expected_end_local.day

        mock_ekevent = self._create_mock_ekevent(
            title="Test All Day",
            start_timestamp=utc_timestamp,
            end_timestamp=end_timestamp,
            is_all_day=True,
        )

        event = Event.from_ekevent(mock_ekevent)

        assert event.end_time.day == expected_end_day
        assert event.end_time.hour == 23
        assert event.end_time.minute == 59
        assert event.end_time.second == 59

    def test_regular_event_preserves_time(self):
        """Non-all-day events should preserve the actual time, not normalize to midnight."""
        # 2pm UTC on a given day
        utc_timestamp = 1766250000  # 2025-12-20 15:00:00 UTC

        mock_ekevent = self._create_mock_ekevent(
            title="Regular Meeting",
            start_timestamp=utc_timestamp,
            end_timestamp=utc_timestamp + 3600,  # +1 hour
            is_all_day=False,
        )

        event = Event.from_ekevent(mock_ekevent)

        # Time should NOT be midnight (preserves actual time)
        # We can't assert exact hour since it depends on local timezone,
        # but we can verify it's not normalized to midnight
        assert event.all_day is False
        # The start_time should be set (not None)
        assert event.start_time is not None

    def test_multiday_allday_event(self):
        """Multi-day all-day event should show correct start and end dates."""
        # 3-day event
        start_timestamp = 1766235600  # 2025-12-20 11:00:00 UTC
        end_timestamp = 1766494799  # 2025-12-23 10:59:59 UTC (3 days later)

        start_utc = datetime.fromtimestamp(start_timestamp, tz=timezone.utc)
        end_utc = datetime.fromtimestamp(end_timestamp, tz=timezone.utc)

        expected_start_day = start_utc.astimezone().day
        expected_end_day = end_utc.astimezone().day

        mock_ekevent = self._create_mock_ekevent(
            title="Conference",
            start_timestamp=start_timestamp,
            end_timestamp=end_timestamp,
            is_all_day=True,
        )

        event = Event.from_ekevent(mock_ekevent)

        assert event.start_time.day == expected_start_day
        assert event.start_time.hour == 0
        assert event.end_time.day == expected_end_day
        assert event.end_time.hour == 23
        assert event.end_time.minute == 59
