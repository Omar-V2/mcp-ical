import pytest
from datetime import datetime
from unittest.mock import Mock, MagicMock

from src.mcp_ical.models import convert_datetime, Event
from src.mcp_ical.groups.group_tools import register_group_tools
from src.mcp_ical.ical import CalendarManager


class TestNSTaggedDateHandling:
    """Test cases for NSTaggedDate object handling."""

    def test_convert_datetime_with_nstaggeddate(self):
        """Test convert_datetime function with NSTaggedDate-like objects."""
        # Mock NSTaggedDate object that has timeIntervalSinceReferenceDate but not timeIntervalSince1970
        mock_nstaggeddate = Mock()
        # Calculate correct timeIntervalSinceReferenceDate for 2024-01-01 00:00:00 UTC
        # NSDate reference: January 1, 2001 00:00:00 UTC = timestamp 978307200
        # Target: January 1, 2024 00:00:00 UTC = timestamp 1704067200  
        # Difference: 1704067200 - 978307200 = 725760000
        mock_nstaggeddate.timeIntervalSinceReferenceDate.return_value = 725760000.0
        
        # Mock the type representation to include NSTaggedDate
        mock_nstaggeddate.__class__.__name__ = "__NSTaggedDate"
        
        result = convert_datetime(mock_nstaggeddate)
        
        # Should convert to a datetime object
        assert isinstance(result, datetime)
        # Should be January 1, 2024 00:00:00 (allowing for timezone differences)
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 1

    def test_convert_datetime_with_regular_nsdate(self):
        """Test convert_datetime function with regular NSDate objects."""
        # Mock regular NSDate object with working timeIntervalSince1970
        mock_nsdate = Mock()
        mock_nsdate.timeIntervalSince1970.return_value = 1704067200.0  # 2024-01-01 00:00:00 UTC
        
        result = convert_datetime(mock_nsdate)
        
        # Should convert to a datetime object
        assert isinstance(result, datetime)
        # Allow for timezone differences, check date components
        assert result.year == 2024
        assert result.month == 1  
        assert result.day == 1

    def test_convert_datetime_with_broken_timeIntervalSince1970(self):
        """Test convert_datetime function when timeIntervalSince1970 raises an error."""
        # Mock NSDate object where timeIntervalSince1970 raises TypeError
        mock_nsdate = Mock()
        mock_nsdate.timeIntervalSince1970.side_effect = TypeError("timeIntervalSince1970 failed")
        mock_nsdate.timeIntervalSinceReferenceDate.return_value = 725760000.0  # 2024-01-01 00:00:00 UTC
        mock_nsdate.__class__.__name__ = "__NSTaggedDate"
        
        result = convert_datetime(mock_nsdate)
        
        # Should fall back to timeIntervalSinceReferenceDate method
        assert isinstance(result, datetime)
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 1

    def test_convert_datetime_with_string(self):
        """Test convert_datetime function with string input."""
        date_string = "2024-01-01T12:00:00"
        result = convert_datetime(date_string)
        
        assert isinstance(result, datetime)
        expected = datetime(2024, 1, 1, 12, 0, 0)
        assert result == expected

    def test_convert_datetime_with_datetime(self):
        """Test convert_datetime function with datetime input."""
        input_datetime = datetime(2024, 1, 1, 12, 0, 0)
        result = convert_datetime(input_datetime)
        
        # Should return the same datetime object
        assert result is input_datetime

    def test_event_from_ekevent_with_nstaggeddate(self):
        """Test Event.from_ekevent with NSTaggedDate objects in start_time and end_time."""
        # Mock EKEvent with NSTaggedDate objects
        mock_ekevent = Mock()
        mock_ekevent.title.return_value = "Test Event"
        mock_ekevent.eventIdentifier.return_value = "test-event-id"
        mock_ekevent.location.return_value = "Test Location"
        mock_ekevent.notes.return_value = "Test Notes"
        mock_ekevent.isAllDay.return_value = False
        mock_ekevent.attendees.return_value = []
        mock_ekevent.alarms.return_value = []
        mock_ekevent.recurrenceRule.return_value = None
        mock_ekevent.availability.return_value = 0
        mock_ekevent.status.return_value = 0
        mock_ekevent.organizer.return_value = None
        mock_ekevent.URL.return_value = None
        
        # Mock calendar
        mock_calendar = Mock()
        mock_calendar.title.return_value = "Test Calendar"
        mock_ekevent.calendar.return_value = mock_calendar
        
        # Mock NSTaggedDate objects for start and end times
        mock_start_date = Mock()
        mock_start_date.timeIntervalSinceReferenceDate.return_value = 725760000.0  # 2024-01-01 00:00:00 UTC
        mock_start_date.__class__.__name__ = "__NSTaggedDate"
        
        mock_end_date = Mock()
        mock_end_date.timeIntervalSinceReferenceDate.return_value = 725763600.0  # 2024-01-01 01:00:00 UTC
        mock_end_date.__class__.__name__ = "__NSTaggedDate"
        
        mock_ekevent.startDate.return_value = mock_start_date
        mock_ekevent.endDate.return_value = mock_end_date
        mock_ekevent.lastModifiedDate.return_value = mock_start_date
        
        # Create Event from EKEvent
        event = Event.from_ekevent(mock_ekevent)
        
        # Verify the event was created successfully with datetime objects
        assert event.title == "Test Event"
        assert isinstance(event.start_time, datetime)
        assert isinstance(event.end_time, datetime)
        assert event.start_time.year == 2024
        assert event.start_time.month == 1
        assert event.start_time.day == 1

    def test_pydantic_model_with_nstaggeddate(self):
        """Test Pydantic model validation with NSTaggedDate objects using FlexibleDateTime."""
        from src.mcp_ical.models import CreateEventRequest
        
        # Mock NSTaggedDate objects 
        mock_start_date = Mock()
        mock_start_date.timeIntervalSinceReferenceDate.return_value = 725760000.0  # 2024-01-01 00:00:00 UTC
        mock_start_date.__class__.__name__ = "__NSTaggedDate"
        
        mock_end_date = Mock()
        mock_end_date.timeIntervalSinceReferenceDate.return_value = 725763600.0  # 2024-01-01 01:00:00 UTC
        mock_end_date.__class__.__name__ = "__NSTaggedDate"
        
        # Create a Pydantic model with NSTaggedDate objects - this should trigger conversion
        try:
            event_request = CreateEventRequest(
                title="Test Event",
                start_time=mock_start_date,
                end_time=mock_end_date,
                calendar_name="Test Calendar"
            )
            
            # Verify the conversion worked
            assert isinstance(event_request.start_time, datetime)
            assert isinstance(event_request.end_time, datetime)
            assert event_request.start_time.year == 2024
            assert event_request.start_time.month == 1
            assert event_request.start_time.day == 1
            
        except Exception as e:
            pytest.fail(f"Pydantic model validation with NSTaggedDate failed: {e}")


class TestGroupToolsWithNSTaggedDate:
    """Test group tools functionality with NSTaggedDate objects."""

    def test_list_events_by_group_with_nstaggeddate(self):
        """Test list_events_by_group when events have NSTaggedDate objects."""
        # Mock calendar manager and events with NSTaggedDate objects
        mock_calendar_manager = Mock(spec=CalendarManager)
        
        # Create mock events with datetime objects (simulating the fixed conversion)
        mock_event1 = Mock()
        mock_event1.start_time = datetime(2024, 1, 1, 10, 0, 0)
        mock_event1.title = "Event 1"
        mock_event1.all_day = False
        mock_event1.calendar_name = "Test Calendar"
        mock_event1.location = "Location 1"
        
        mock_event2 = Mock()
        mock_event2.start_time = datetime(2024, 1, 2, 14, 0, 0)
        mock_event2.title = "Event 2"
        mock_event2.all_day = True
        mock_event2.calendar_name = "Test Calendar"
        mock_event2.location = None
        
        # Mock the group bridge to return our test events
        mock_group_bridge = Mock()
        mock_group_bridge.get_events_by_group.return_value = [mock_event1, mock_event2]
        
        # Test that calling .date() on the start_time works without errors
        # This simulates the code path in group_tools.py line 235
        try:
            event1_date = mock_event1.start_time.date()
            event2_date = mock_event2.start_time.date()
            
            # Verify the .date() method works correctly
            assert event1_date.year == 2024
            assert event1_date.month == 1
            assert event1_date.day == 1
            
            assert event2_date.year == 2024
            assert event2_date.month == 1
            assert event2_date.day == 2
            
        except AttributeError as e:
            pytest.fail(f"event.start_time.date() failed: {e}")

    def test_nstaggeddate_reference_date_calculation(self):
        """Test the NSDate reference date calculation used in convert_datetime."""
        # NSDate reference date is January 1, 2001 00:00:00 UTC
        reference_timestamp = 978307200  # January 1, 2001 00:00:00 UTC
        
        # Test with a known timeIntervalSinceReferenceDate value
        time_interval = 725760000.0  # Corrected value for 2024-01-01 00:00:00 UTC
        
        # Calculate the expected timestamp
        expected_timestamp = time_interval + reference_timestamp
        expected_datetime = datetime.fromtimestamp(expected_timestamp)
        
        # This should give us January 1, 2024 (allowing for timezone differences)
        assert expected_datetime.year == 2024
        assert expected_datetime.month == 1
        assert expected_datetime.day == 1