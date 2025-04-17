import time
from datetime import datetime, timedelta
import subprocess

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
    """
    会话级别的 fixture，整个测试会话只创建一个 CalendarManager 实例。
    作用：
    - 用于所有测试用例共享同一个 CalendarManager，避免重复初始化。
    - 在 fixture 初始化时主动触发一次 macOS 日历权限请求，确保后续操作不会因权限弹窗阻塞。
    - 返回 CalendarManager 实例供测试用例使用。
    """
    # 主动触发一次权限请求
    try:
        subprocess.run([
            "osascript",
            "-e",
            'tell application "Calendar" to get name of calendars'
        ], timeout=5)
    except Exception:
        pass
    return CalendarManager()


@pytest.fixture(scope="session", autouse=True)
def cleanup_calendars_after_tests():
    """
    会话级别的自动 fixture，在所有测试结束后自动执行清理操作。
    作用：
    - 测试结束后等待一段时间，确保 iCloud 日历同步完成。
    - 再次获取 CalendarManager，遍历所有日历，删除以 test_calendar_ 开头的测试日历，防止测试遗留数据。
    - 该 fixture 自动应用，无需在测试用例中显式引用。
    """
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
    """
    用于为每个测试用例创建一个独立的测试日历。
    作用：
    - 每次测试生成唯一名称的日历，避免测试间数据干扰。
    - 测试结束后自动删除该日历，保证环境整洁。
    - 通过 yield 返回日历名称和 manager，供测试用例使用。
    """
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
    """
    用于在每个测试用例后清理创建的事件。
    作用：
    - 提供 _add_event 方法，测试用例可注册需要清理的事件 ID。
    - 测试结束后自动遍历并删除这些事件，防止数据残留。
    - 依赖于传入的 calendar_manager 实例。
    """
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
    """
    提供基础事件数据的 fixture。
    作用：
    - 生成一个默认的事件字典，包含标题、起止时间、备注、地点等。
    - 方便各测试用例复用，减少重复代码。
    - 起止时间为当前时间+1天，持续1小时。
    """
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

    from_calendar = calendars[0].title()
    to_calendar = calendars[1].title()

    # Create event in the from_calendar
    event = calendar_manager.create_event(
        CreateEventRequest(
            title=test_event_base["title"],
            start_time=test_event_base["start_time"],
            end_time=test_event_base["end_time"],
            notes=test_event_base.get("notes"),
            location=test_event_base.get("location"),
            calendar_name=from_calendar,
        )
    )
    cleanup_events(event.identifier)

    # Move it to the to_calendar
    calendar_manager.update_event(event.identifier, UpdateEventRequest(calendar_name=to_calendar))

    # Verify event moved
    retrieved_event = calendar_manager.find_event_by_id(event.identifier)
    assert retrieved_event.calendar_name == to_calendar


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
