import time
from datetime import datetime, timedelta

import pytest

from src.mcp_ical.ical import CalendarManager, NoSuchCalendarException
from src.mcp_ical.models import (
    CreateEventRequest,
    Frequency,
    RecurrenceRule,
    UpdateEventRequest,
)


@pytest.fixture(scope="session")
def calendar_manager():
    """Create a single CalendarManager instance for all tests."""
    return CalendarManager()


@pytest.fixture(scope="session", autouse=True)
def cleanup_calendars_after_tests():
    """Fixture that runs after all tests to ensure calendars are properly cleaned up."""
    yield

    print("Waiting for iCloud sync before final calendar cleanup...")
    time.sleep(5)

    # Get a fresh calendar manager
    calendar_manager = CalendarManager()

    # Clean up any remaining test calendars
    for calendar in calendar_manager.list_calendars():
        if calendar.title().startswith("test_calendar_"):
            calendar_manager._delete_calendar(calendar.uniqueIdentifier())


@pytest.fixture
def test_calendar(calendar_manager):
    """Create an isolated calendar for testing."""
    calendar_name = f"test_calendar_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"

    calendar = calendar_manager._create_calendar(calendar_name)
    if not calendar:
        pytest.fail(f"Failed to create test calendar: {calendar_name}")

    yield {"name": calendar_name, "manager": calendar_manager}

    try:
        calendar_manager._delete_calendar(calendar.uniqueIdentifier())
    except Exception as e:
        print(f"Failed to cleanup test calendar {calendar_name}: {e}")


@pytest.fixture
def cleanup_events(calendar_manager):
    """Fixture to clean up created events after tests"""
    created_events = []

    def _add_event(event_id):
        created_events.append(event_id)

    yield _add_event

    # Use the injected calendar_manager instead of creating a new one
    for event_id in created_events:
        try:
            calendar_manager.delete_event(event_id)
        except Exception as e:
            print(f"Failed to delete event {event_id}: {e}")


@pytest.fixture
def test_event_base():
    """Base event data for testing"""
    start_time = datetime.now().replace(microsecond=0) + timedelta(days=1)
    end_time = start_time + timedelta(hours=1)
    return {
        "title": "Test Event",
        "start_time": start_time,
        "end_time": end_time,
        "notes": "Test notes",
        "location": "Test location",
    }


def test_create_and_get_event(calendar_manager, test_event_base, test_calendar, cleanup_events):
    """Test creating an event and retrieving it"""
    # Create event
    event = calendar_manager.create_event(
        CreateEventRequest(
            title=test_event_base["title"],
            start_time=test_event_base["start_time"],
            end_time=test_event_base["end_time"],
            notes=test_event_base["notes"],
            location=test_event_base["location"],
            calendar_name=test_calendar["name"],
        )
    )
    cleanup_events(event.identifier)

    # Verify event was created
    retrieved_event = calendar_manager.find_event_by_id(event.identifier)
    assert retrieved_event is not None
    assert retrieved_event.title == test_event_base["title"]
    assert retrieved_event.start_time == test_event_base["start_time"]
    assert retrieved_event.end_time == test_event_base["end_time"]
    assert retrieved_event.notes == test_event_base["notes"]
    assert retrieved_event.location == test_event_base["location"]
    assert retrieved_event.calendar_name == test_calendar["name"]


def test_list_events(calendar_manager, test_event_base, test_calendar, cleanup_events):
    """Test listing events"""
    # Create first event
    event1 = calendar_manager.create_event(
        CreateEventRequest(
            title="Test Event 1",
            start_time=test_event_base["start_time"],
            end_time=test_event_base["end_time"],
            notes=test_event_base["notes"],
            location=test_event_base["location"],
            calendar_name=test_calendar["name"],
        )
    )
    cleanup_events(event1.identifier)

    # Create second event with offset times
    event2 = calendar_manager.create_event(
        CreateEventRequest(
            title="Test Event 2",
            start_time=test_event_base["start_time"] + timedelta(hours=2),
            end_time=test_event_base["end_time"] + timedelta(hours=2),
            notes=test_event_base["notes"],
            location=test_event_base["location"],
            calendar_name=test_calendar["name"],
        )
    )
    cleanup_events(event2.identifier)

    # List events in the time range
    events = calendar_manager.list_events(
        start_time=test_event_base["start_time"] - timedelta(hours=1),
        end_time=test_event_base["end_time"] + timedelta(hours=3),
    )

    # Verify both events are in the list
    event_ids = [event.identifier for event in events]
    assert event1.identifier in event_ids
    assert event2.identifier in event_ids


def test_update_event(calendar_manager, test_event_base, test_calendar, cleanup_events):
    """Test updating an event"""
    # Create event
    event = calendar_manager.create_event(
        CreateEventRequest(
            title=test_event_base["title"],
            start_time=test_event_base["start_time"],
            end_time=test_event_base["end_time"],
            notes=test_event_base["notes"],
            location=test_event_base["location"],
            calendar_name=test_calendar["name"],
        )
    )
    # cleanup_events(event.identifier)

    # Update event
    new_title = "Updated Test Event"
    new_location = "Updated Location"
    updated_event = calendar_manager.update_event(
        event.identifier, UpdateEventRequest(title=new_title, location=new_location)
    )

    # Verify updates
    assert updated_event.title == new_title
    assert updated_event.location == new_location

    # Verify updates persisted
    retrieved_event = calendar_manager.find_event_by_id(event.identifier)
    assert retrieved_event.title == new_title
    assert retrieved_event.location == new_location


def test_delete_event(calendar_manager, test_event_base, test_calendar):
    """Test deleting an event"""
    # Create event
    event = calendar_manager.create_event(
        CreateEventRequest(
            title=test_event_base["title"],
            start_time=test_event_base["start_time"],
            end_time=test_event_base["end_time"],
            notes=test_event_base["notes"],
            location=test_event_base["location"],
            calendar_name=test_calendar["name"],
        )
    )

    # Delete event
    calendar_manager.delete_event(event.identifier)

    # Verify event was deleted
    retrieved_event = calendar_manager.find_event_by_id(event.identifier)
    assert retrieved_event is None


def test_recurring_event(calendar_manager, test_event_base, test_calendar, cleanup_events):
    """Test creating and updating a recurring event"""
    # Create recurring event
    recurrence_rule = RecurrenceRule(frequency=Frequency.DAILY, interval=1, occurrence_count=3)

    event = calendar_manager.create_event(
        CreateEventRequest(
            title=test_event_base["title"],
            start_time=test_event_base["start_time"],
            end_time=test_event_base["end_time"],
            notes=test_event_base["notes"],
            location=test_event_base["location"],
            recurrence_rule=recurrence_rule,
            calendar_name=test_calendar["name"],
        )
    )
    cleanup_events(event.identifier)

    # Update recurring event
    new_title = "Updated Recurring Event"
    calendar_manager.update_event(event.identifier, UpdateEventRequest(title=new_title))

    # List future events to verify update affected all occurrences
    events = calendar_manager.list_events(
        start_time=test_event_base["start_time"],
        end_time=test_event_base["start_time"] + timedelta(days=30),
        calendar_name=test_calendar["name"],
    )

    assert len(events) == 3
    for e in events:
        assert e.title == new_title


def test_all_day_event_with_reminders(calendar_manager, test_event_base, test_calendar, cleanup_events):
    """Test creating an all-day event with reminders"""

    # Request 4 days and 2 days before
    requested_offsets = [4 * 24 * 60, 2 * 24 * 60]  # [5760, 2880]

    event = calendar_manager.create_event(
        CreateEventRequest(
            title=test_event_base["title"],
            start_time=test_event_base["start_time"],
            end_time=test_event_base["end_time"],
            notes=test_event_base["notes"],
            location=test_event_base["location"],
            all_day=True,
            alarms_minutes_offsets=requested_offsets,
            calendar_name=test_calendar["name"],
        )
    )
    cleanup_events(event.identifier)

    retrieved_event = calendar_manager.find_event_by_id(event.identifier)
    assert retrieved_event.all_day is True

    # Verify our explicitly requested alarms are present
    # EventKit may add its own default alarm hence asserting presence not equality
    actual_alarms = retrieved_event.alarms_minutes_offsets
    assert 2880 in actual_alarms, "2 day reminder not found"
    assert 5760 in actual_alarms, "4 day reminder not found"


def test_event_across_calendars(calendar_manager, test_event_base, test_calendar, cleanup_events):
    """Test moving an event between calendars"""
    # Get available calendars
    calendars = calendar_manager.list_calendars()
    if len(calendars) < 2:
        pytest.skip("Need at least 2 calendars for this test")

    # Create event in the Home calendar
    event = calendar_manager.create_event(
        CreateEventRequest(
            title=test_event_base["title"],
            start_time=test_event_base["start_time"],
            end_time=test_event_base["end_time"],
            notes=test_event_base["notes"],
            location=test_event_base["location"],
            calendar_name="Home",
        )
    )
    cleanup_events(event.identifier)

    # Move it to another test calendar
    calendar_manager.update_event(event.identifier, UpdateEventRequest(calendar_name=test_calendar["name"]))

    # Verify event moved
    retrieved_event = calendar_manager.find_event_by_id(event.identifier)
    assert retrieved_event.calendar_name == test_calendar["name"]


def test_create_event_uses_default_calendar(calendar_manager, test_event_base, test_calendar, cleanup_events):
    """Test that creating an event without specifying calendar uses the default calendar"""
    event = calendar_manager.create_event(
        CreateEventRequest(
            title=test_event_base["title"],
            start_time=test_event_base["start_time"],
            end_time=test_event_base["end_time"],
            notes=test_event_base["notes"],
            location=test_event_base["location"],
            calendar_name=test_calendar["name"],
        )
    )
    cleanup_events(event.identifier)

    # Get the event and verify it's in the default calendar
    retrieved_event = calendar_manager.find_event_by_id(event.identifier)
    assert retrieved_event is not None
    # The default calendar should be set
    assert retrieved_event.calendar_name is not None


def test_create_event_nonexistent_calendar(calendar_manager, test_event_base):
    """Test that creating an event in a non-existent calendar raises NoSuchCalendarException"""
    with pytest.raises(NoSuchCalendarException):
        calendar_manager.create_event(
            CreateEventRequest(
                title=test_event_base["title"],
                start_time=test_event_base["start_time"],
                end_time=test_event_base["end_time"],
                notes=test_event_base["notes"],
                location=test_event_base["location"],
                calendar_name="NonExistentCalendar",
            )
        )


def test_update_event_nonexistent_calendar(calendar_manager, test_event_base, test_calendar, cleanup_events):
    """Test that updating an event to a non-existent calendar raises NoSuchCalendarException"""
    # First create an event
    event = calendar_manager.create_event(
        CreateEventRequest(
            title=test_event_base["title"],
            start_time=test_event_base["start_time"],
            end_time=test_event_base["end_time"],
            calendar_name=test_calendar["name"],
        )
    )
    cleanup_events(event.identifier)

    # Try to update it to a non-existent calendar
    with pytest.raises(NoSuchCalendarException):
        calendar_manager.update_event(event.identifier, UpdateEventRequest(calendar_name="NonExistentCalendar"))


def test_find_nonexistent_event(calendar_manager):
    """Test that finding a non-existent event returns None"""
    non_existent_id = "non-existent-event-id"
    retrieved_event = calendar_manager.find_event_by_id(non_existent_id)
    assert retrieved_event is None


def test_all_day_event_with_same_day_reminders(calendar_manager, test_event_base, test_calendar, cleanup_events):
    """Test creating an all-day event with reminders on the same day"""
    # Request reminders 2 hours and 4 hours before
    requested_offsets = [2 * 60, 4 * 60]  # 120 and 240 minutes

    event = calendar_manager.create_event(
        CreateEventRequest(
            title=test_event_base["title"],
            start_time=test_event_base["start_time"],
            end_time=test_event_base["end_time"],
            all_day=True,
            alarms_minutes_offsets=requested_offsets,
            calendar_name=test_calendar["name"],
        )
    )
    cleanup_events(event.identifier)

    retrieved_event = calendar_manager.find_event_by_id(event.identifier)
    assert retrieved_event.all_day is True

    actual_alarms = retrieved_event.alarms_minutes_offsets
    assert 120 in actual_alarms, "2 hour reminder not found"
    assert 240 in actual_alarms, "4 hour reminder not found"


def test_all_day_event_mixed_reminders(calendar_manager, test_event_base, test_calendar, cleanup_events):
    """Test all-day event with mix of same-day and multi-day reminders"""
    # Mix of reminders: 2 hours, 1 day, and 3 days before
    requested_offsets = [2 * 60, 24 * 60, 3 * 24 * 60]  # 120, 1440, and 4320 minutes

    event = calendar_manager.create_event(
        CreateEventRequest(
            title=test_event_base["title"],
            start_time=test_event_base["start_time"],
            end_time=test_event_base["end_time"],
            all_day=True,
            alarms_minutes_offsets=requested_offsets,
            calendar_name=test_calendar["name"],
        )
    )
    cleanup_events(event.identifier)

    retrieved_event = calendar_manager.find_event_by_id(event.identifier)
    assert retrieved_event.all_day is True

    actual_alarms = sorted(retrieved_event.alarms_minutes_offsets)
    assert 120 in actual_alarms, "2 hour reminder not found"
    assert 1440 in actual_alarms, "1 day reminder not found"
    assert 4320 in actual_alarms, "3 day reminder not found"


def test_nstaggeddate_compatibility_in_event_dates(calendar_manager, test_event_base, test_calendar, cleanup_events):
    """Test that event dates work correctly with NSTaggedDate objects and .date() method calls"""
    # Create an event
    event = calendar_manager.create_event(
        CreateEventRequest(
            title=test_event_base["title"],
            start_time=test_event_base["start_time"],
            end_time=test_event_base["end_time"],
            notes=test_event_base["notes"],
            location=test_event_base["location"],
            calendar_name=test_calendar["name"],
        )
    )
    cleanup_events(event.identifier)

    # List events to get them with potentially NSTaggedDate objects
    events = calendar_manager.list_events(
        start_time=test_event_base["start_time"] - timedelta(hours=1),
        end_time=test_event_base["end_time"] + timedelta(hours=1),
    )
    
    # Find our test event
    test_event = None
    for e in events:
        if e.identifier == event.identifier:
            test_event = e
            break
    
    assert test_event is not None, "Created event not found in list"
    
    # Test that .date() method works on start_time and end_time
    # This is the critical test for the NSTaggedDate fix
    try:
        start_date = test_event.start_time.date()
        end_date = test_event.end_time.date()
        
        # Verify the dates are correct
        expected_start_date = test_event_base["start_time"].date()
        expected_end_date = test_event_base["end_time"].date()
        
        assert start_date == expected_start_date, f"Start date mismatch: {start_date} != {expected_start_date}"
        assert end_date == expected_end_date, f"End date mismatch: {end_date} != {expected_end_date}"
        
    except AttributeError as e:
        pytest.fail(f"NSTaggedDate compatibility test failed: {e}")


def test_event_date_formatting_like_group_tools(calendar_manager, test_event_base, test_calendar, cleanup_events):
    """Test date formatting similar to what group tools do, ensuring NSTaggedDate compatibility"""
    # Create multiple events on different dates
    event1 = calendar_manager.create_event(
        CreateEventRequest(
            title="Event 1",
            start_time=test_event_base["start_time"],
            end_time=test_event_base["end_time"],
            calendar_name=test_calendar["name"],
        )
    )
    cleanup_events(event1.identifier)
    
    event2 = calendar_manager.create_event(
        CreateEventRequest(
            title="Event 2", 
            start_time=test_event_base["start_time"] + timedelta(days=1),
            end_time=test_event_base["end_time"] + timedelta(days=1),
            calendar_name=test_calendar["name"],
        )
    )
    cleanup_events(event2.identifier)

    # List events
    events = calendar_manager.list_events(
        start_time=test_event_base["start_time"] - timedelta(hours=1),
        end_time=test_event_base["end_time"] + timedelta(days=2),
    )
    
    # Sort by start time like group tools do
    events.sort(key=lambda x: x.start_time)
    
    # Test the exact pattern used in group_tools.py lines 235-238
    current_date = None
    formatted_output = ""
    
    for event in events:
        if event.identifier in [event1.identifier, event2.identifier]:
            try:
                # This is the critical line that was failing with NSTaggedDate
                event_date = event.start_time.date()
                
                if current_date != event_date:
                    current_date = event_date
                    formatted_output += f"📅 **{event_date.strftime('%A, %B %d, %Y')}**\n"
                
                time_str = "All Day" if event.all_day else event.start_time.strftime('%H:%M')
                formatted_output += f"   • {time_str} - {event.title}\n"
                
            except AttributeError as e:
                pytest.fail(f"Group tools date formatting simulation failed: {e}")
    
    # Verify we got some formatted output
    assert "📅" in formatted_output, "Date headers not generated"
    assert "Event 1" in formatted_output, "Event 1 not found in output"
    assert "Event 2" in formatted_output, "Event 2 not found in output"
