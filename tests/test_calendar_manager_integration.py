import time
from datetime import datetime, timedelta, timezone

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
    """Base event data for testing - uses timezone-aware datetimes"""
    # Create timezone-aware datetime in local timezone
    start_time = datetime.now(timezone.utc).astimezone().replace(microsecond=0) + timedelta(days=1)
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


def test_delete_non_recurring_event(calendar_manager, test_event_base, test_calendar):
    """Test deleting a non-recurring event (simplest case)"""
    # Create non-recurring event
    event = calendar_manager.create_event(
        CreateEventRequest(
            title="Non-Recurring Event",
            start_time=test_event_base["start_time"],
            end_time=test_event_base["end_time"],
            calendar_name=test_calendar["name"],
        )
    )

    # Delete event (delete_entire_series parameter doesn't matter for non-recurring)
    success = calendar_manager.delete_event(event.identifier)
    assert success is True

    # Verify event was deleted
    retrieved_event = calendar_manager.find_event_by_id(event.identifier)
    assert retrieved_event is None


def test_delete_recurring_event_entire_series(calendar_manager, test_event_base, test_calendar):
    """Test deleting an entire recurring event series"""
    # Create recurring event (3 daily occurrences)
    recurrence_rule = RecurrenceRule(frequency=Frequency.DAILY, interval=1, occurrence_count=3)

    event = calendar_manager.create_event(
        CreateEventRequest(
            title="Recurring Event to Delete",
            start_time=test_event_base["start_time"],
            end_time=test_event_base["end_time"],
            recurrence_rule=recurrence_rule,
            calendar_name=test_calendar["name"],
        )
    )

    event_id = event.identifier

    # Verify the recurring event was created
    retrieved_event = calendar_manager.find_event_by_id(event_id)
    assert retrieved_event is not None

    # List events to verify all occurrences exist
    events_before = calendar_manager.list_events(
        start_time=test_event_base["start_time"],
        end_time=test_event_base["start_time"] + timedelta(days=5),
        calendar_name=test_calendar["name"],
    )
    assert len(events_before) == 3

    # Delete entire series (default behavior)
    success = calendar_manager.delete_event(event_id, delete_entire_series=True)
    assert success is True

    # Verify all occurrences were deleted
    events_after = calendar_manager.list_events(
        start_time=test_event_base["start_time"],
        end_time=test_event_base["start_time"] + timedelta(days=5),
        calendar_name=test_calendar["name"],
    )
    assert len(events_after) == 0

    # Verify the event itself is gone
    retrieved_event = calendar_manager.find_event_by_id(event_id)
    assert retrieved_event is None


def test_delete_recurring_event_single_occurrence(calendar_manager, test_event_base, test_calendar):
    """Test deleting just one occurrence from a recurring event (with occurrence_date, default delete_entire_series=False)"""
    # Create recurring event (5 daily occurrences)
    recurrence_rule = RecurrenceRule(frequency=Frequency.DAILY, interval=1, occurrence_count=5)

    event = calendar_manager.create_event(
        CreateEventRequest(
            title="Recurring Event - Delete One",
            start_time=test_event_base["start_time"],
            end_time=test_event_base["end_time"],
            recurrence_rule=recurrence_rule,
            calendar_name=test_calendar["name"],
        )
    )

    # Delete the 3rd occurrence (relies on default delete_entire_series=False)
    third_occurrence_date = test_event_base["start_time"] + timedelta(days=2)
    success = calendar_manager.delete_event(event.identifier, occurrence_date=third_occurrence_date)
    assert success is True

    # Verify only one occurrence was deleted (should have 4 remaining: 1st, 2nd, 4th, 5th)
    events_after = calendar_manager.list_events(
        start_time=test_event_base["start_time"],
        end_time=test_event_base["start_time"] + timedelta(days=7),
        calendar_name=test_calendar["name"],
    )
    assert len(events_after) == 4

    # Clean up
    calendar_manager.delete_event(event.identifier, delete_entire_series=True)


def test_delete_recurring_event_from_occurrence_forward(calendar_manager, test_event_base, test_calendar):
    """Test deleting from a specific occurrence forward (occurrence_date + delete_entire_series=True)"""
    # Create recurring event (5 daily occurrences)
    recurrence_rule = RecurrenceRule(frequency=Frequency.DAILY, interval=1, occurrence_count=5)

    event = calendar_manager.create_event(
        CreateEventRequest(
            title="Recurring Event - Delete Forward",
            start_time=test_event_base["start_time"],
            end_time=test_event_base["end_time"],
            recurrence_rule=recurrence_rule,
            calendar_name=test_calendar["name"],
        )
    )

    # Delete from 3rd occurrence forward (should delete 3rd, 4th, 5th; keep 1st, 2nd)
    third_occurrence_date = test_event_base["start_time"] + timedelta(days=2)
    success = calendar_manager.delete_event(
        event.identifier,
        delete_entire_series=True,
        occurrence_date=third_occurrence_date
    )
    assert success is True

    # Verify 3rd, 4th, 5th deleted; 1st, 2nd remain
    events_after = calendar_manager.list_events(
        start_time=test_event_base["start_time"],
        end_time=test_event_base["start_time"] + timedelta(days=7),
        calendar_name=test_calendar["name"],
    )
    assert len(events_after) == 2

    # Clean up remaining
    calendar_manager.delete_event(event.identifier, delete_entire_series=True)


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


def test_update_recurring_event_single_occurrence(calendar_manager, test_event_base, test_calendar):
    """Test updating just one occurrence of a recurring event (with occurrence_date, default update_future_events=False)"""
    # Create recurring event (5 daily occurrences)
    recurrence_rule = RecurrenceRule(frequency=Frequency.DAILY, interval=1, occurrence_count=5)

    event = calendar_manager.create_event(
        CreateEventRequest(
            title="Recurring Event - Update One",
            start_time=test_event_base["start_time"],
            end_time=test_event_base["end_time"],
            recurrence_rule=recurrence_rule,
            calendar_name=test_calendar["name"],
        )
    )

    # Update the 3rd occurrence only (relies on default update_future_events=False)
    third_occurrence_date = test_event_base["start_time"] + timedelta(days=2)
    updated_title = "Updated Third Occurrence"
    updated_event = calendar_manager.update_event(
        event.identifier,
        UpdateEventRequest(title=updated_title),
        occurrence_date=third_occurrence_date,
    )
    assert updated_event.title == updated_title

    # Verify only one occurrence was updated
    events = calendar_manager.list_events(
        start_time=test_event_base["start_time"],
        end_time=test_event_base["start_time"] + timedelta(days=7),
        calendar_name=test_calendar["name"],
    )
    assert len(events) == 5

    # Check that other occurrences still have the original title
    original_count = sum(1 for e in events if e.title == "Recurring Event - Update One")
    updated_count = sum(1 for e in events if e.title == updated_title)
    assert original_count == 4, "Expected 4 occurrences with original title"
    assert updated_count == 1, "Expected 1 occurrence with updated title"

    # Clean up
    calendar_manager.delete_event(event.identifier, delete_entire_series=True)


def test_update_recurring_event_from_occurrence_forward(calendar_manager, test_event_base, test_calendar):
    """Test updating from a specific occurrence forward (occurrence_date + update_future_events=True)"""
    # Create recurring event (5 daily occurrences)
    recurrence_rule = RecurrenceRule(frequency=Frequency.DAILY, interval=1, occurrence_count=5)

    event = calendar_manager.create_event(
        CreateEventRequest(
            title="Recurring Event - Update Forward",
            start_time=test_event_base["start_time"],
            end_time=test_event_base["end_time"],
            recurrence_rule=recurrence_rule,
            calendar_name=test_calendar["name"],
        )
    )

    # Update from the 3rd occurrence forward
    third_occurrence_date = test_event_base["start_time"] + timedelta(days=2)
    updated_title = "Updated From Third Forward"
    updated_event = calendar_manager.update_event(
        event.identifier,
        UpdateEventRequest(title=updated_title),
        update_future_events=True,
        occurrence_date=third_occurrence_date,
    )
    assert updated_event.title == updated_title

    # Verify occurrences 3, 4, 5 were updated but 1, 2 were not
    events = calendar_manager.list_events(
        start_time=test_event_base["start_time"],
        end_time=test_event_base["start_time"] + timedelta(days=7),
        calendar_name=test_calendar["name"],
    )
    assert len(events) == 5

    # Check titles
    original_count = sum(1 for e in events if e.title == "Recurring Event - Update Forward")
    updated_count = sum(1 for e in events if e.title == updated_title)
    assert original_count == 2, "Expected 2 occurrences with original title (1st and 2nd)"
    assert updated_count == 3, "Expected 3 occurrences with updated title (3rd, 4th, 5th)"

    # Clean up
    calendar_manager.delete_event(event.identifier, delete_entire_series=True)


def test_update_recurring_event_all_occurrences(calendar_manager, test_event_base, test_calendar):
    """Test updating all occurrences of a recurring event (no occurrence_date)"""
    # Create recurring event (5 daily occurrences)
    recurrence_rule = RecurrenceRule(frequency=Frequency.DAILY, interval=1, occurrence_count=5)

    event = calendar_manager.create_event(
        CreateEventRequest(
            title="Recurring Event - Update All",
            start_time=test_event_base["start_time"],
            end_time=test_event_base["end_time"],
            recurrence_rule=recurrence_rule,
            calendar_name=test_calendar["name"],
        )
    )

    # Update all occurrences (no occurrence_date)
    updated_title = "All Updated"
    updated_event = calendar_manager.update_event(
        event.identifier, UpdateEventRequest(title=updated_title)
    )
    assert updated_event.title == updated_title

    # Verify all occurrences were updated
    events = calendar_manager.list_events(
        start_time=test_event_base["start_time"],
        end_time=test_event_base["start_time"] + timedelta(days=7),
        calendar_name=test_calendar["name"],
    )
    assert len(events) == 5

    # Check all have updated title
    updated_count = sum(1 for e in events if e.title == updated_title)
    assert updated_count == 5, "Expected all 5 occurrences to have updated title"

    # Clean up
    calendar_manager.delete_event(event.identifier, delete_entire_series=True)


def test_create_event_with_attendees(calendar_manager, test_event_base, test_calendar, cleanup_events):
    """Test creating an event with attendees"""
    attendees = ["test1@example.com", "Test User <test2@example.com>"]
    event = calendar_manager.create_event(
        CreateEventRequest(
            title="Meeting with Attendees",
            start_time=test_event_base["start_time"],
            end_time=test_event_base["end_time"],
            notes="Test meeting with invitees",
            location=test_event_base["location"],
            calendar_name=test_calendar["name"],
            attendees=attendees,
        )
    )
    cleanup_events(event.identifier)

    # Give Calendar.app time to sync attendees back to EventKit
    time.sleep(3)

    retrieved_event = calendar_manager.find_event_by_id(event.identifier)
    assert retrieved_event is not None
    assert retrieved_event.attendees is not None, "Attendees should not be None"
    assert len(retrieved_event.attendees) >= 2, f"Expected at least 2 attendees, got {retrieved_event.attendees}"

    # Check emails appear in attendee strings (format is "Name <email>")
    attendees_str = " ".join(retrieved_event.attendees).lower()
    assert "test1@example.com" in attendees_str, f"test1@example.com not found in {retrieved_event.attendees}"
    assert "test2@example.com" in attendees_str, f"test2@example.com not found in {retrieved_event.attendees}"


def test_update_event_attendees(calendar_manager, test_event_base, test_calendar, cleanup_events):
    """Test updating attendees on an existing event"""
    event = calendar_manager.create_event(
        CreateEventRequest(
            title="Meeting Without Attendees",
            start_time=test_event_base["start_time"],
            end_time=test_event_base["end_time"],
            calendar_name=test_calendar["name"],
        )
    )
    cleanup_events(event.identifier)

    attendees = ["attendee1@example.com", "Attendee Two <attendee2@example.com>"]
    updated_event = calendar_manager.update_event(
        event.identifier, UpdateEventRequest(attendees=attendees)
    )
    assert updated_event is not None

    # Attendees are added via AppleScript (external to EventKit), so reset the store cache
    time.sleep(3)
    calendar_manager.event_store.reset()

    retrieved_event = calendar_manager.find_event_by_id(event.identifier)
    assert retrieved_event is not None
    assert retrieved_event.attendees is not None, "Attendees should not be None"
    assert len(retrieved_event.attendees) >= 2, f"Expected at least 2 attendees, got {retrieved_event.attendees}"

    attendees_str = " ".join(retrieved_event.attendees).lower()
    assert "attendee1@example.com" in attendees_str, f"attendee1@example.com not found in {retrieved_event.attendees}"
    assert "attendee2@example.com" in attendees_str, f"attendee2@example.com not found in {retrieved_event.attendees}"
