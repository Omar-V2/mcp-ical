import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from threading import Semaphore
from typing import Any

from EventKit import (
    EKAlarm,  # type: ignore
    EKCalendar,  # type: ignore
    EKEntityTypeEvent,  # type: ignore
    EKEvent,  # type: ignore
    EKEventStore,  # type: ignore
    EKSpanFutureEvents,  # type: ignore
    EKSpanThisEvent,  # type: ignore
)
from loguru import logger

from .models import (
    CreateEventRequest,
    Event,
    UpdateEventRequest,
)

logger.remove()
logger.add(
    sys.stderr,
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
    level="DEBUG",
)


def to_eventkit_datetime(dt: datetime) -> datetime:
    """Convert a datetime to naive local time for EventKit.

    EventKit expects naive datetime objects in local timezone. This function:
    1. Converts timezone-aware datetimes to local timezone, then strips tzinfo
    2. Passes through naive datetimes as-is (assumes they're already local)

    Args:
        dt: datetime object (aware or naive)

    Returns:
        datetime: Naive datetime in local timezone suitable for EventKit

    Examples:
        >>> # Timezone-aware UTC time
        >>> utc_dt = datetime(2025, 11, 14, 3, 0, tzinfo=timezone.utc)
        >>> to_eventkit_datetime(utc_dt)
        datetime(2025, 11, 14, 14, 0)  # AEDT is UTC+11

        >>> # Timezone-aware PST time
        >>> pst_dt = datetime(2025, 11, 14, 10, 0, tzinfo=ZoneInfo('America/Los_Angeles'))
        >>> to_eventkit_datetime(pst_dt)
        datetime(2025, 11, 15, 5, 0)  # Converted to AEDT

        >>> # Naive datetime (assumed local)
        >>> naive_dt = datetime(2025, 11, 14, 14, 0)
        >>> to_eventkit_datetime(naive_dt)
        datetime(2025, 11, 14, 14, 0)  # Passed through
    """
    if dt.tzinfo is not None:
        # Timezone-aware: convert to local timezone and strip tzinfo
        return dt.astimezone().replace(tzinfo=None)
    # Naive: pass through as-is (assume it's already local time)
    return dt


_calendar_app_last_launch: float = 0.0
_CALENDAR_APP_COOLDOWN = 30  # seconds


def _ensure_calendar_app():
    """Launch Calendar.app if it hasn't been launched in the last 30 seconds."""
    global _calendar_app_last_launch
    now = time.monotonic()
    if now - _calendar_app_last_launch > _CALENDAR_APP_COOLDOWN:
        subprocess.run(["open", "-g", "-a", "Calendar"], check=False, timeout=5)
        _calendar_app_last_launch = now


def add_attendees_via_applescript(
    attendee_emails: list[str],
    event_title: str,
    calendar_name: str,
    start_date: datetime,
) -> None:
    """Add attendees to an existing calendar event using AppleScript.

    EventKit's attendees property is read-only, but macOS Calendar.app's AppleScript
    interface supports adding attendees. This function uses AppleScript to add
    attendees to an already-created event, matching by calendar + title + start date.

    Args:
        attendee_emails: List of email addresses (can be "Name <email@example.com>" format)
        event_title: The title/summary of the event
        calendar_name: The calendar the event belongs to
        start_date: The start date of the event (naive local time, as from EventKit)
    """
    if not attendee_emails:
        return

    # Ensure Calendar.app is running (rate-limited to avoid crash-inducing rapid launches).
    # Google CalDAV calendars need ~8s for Calendar.app to pick up EventKit changes.
    _ensure_calendar_app()
    time.sleep(8)

    # Build list of attendees for AppleScript
    attendees_data = []
    for email_str in attendee_emails:
        email_str = email_str.strip()
        if "<" in email_str and ">" in email_str:
            parts = email_str.split("<")
            name = parts[0].strip().replace('"', '\\"')
            email = parts[1].replace(">", "").strip()
        else:
            email = email_str
            name = email.split("@")[0] if "@" in email else email
        attendees_data.append((name, email))

    escaped_title = event_title.replace('"', '\\"')
    escaped_calendar = calendar_name.replace('"', '\\"')

    attendees_list = ", ".join(
        [f'{{email:"{email}", display name:"{name}"}}' for name, email in attendees_data]
    )

    # Convert start_date to a Python datetime for AppleScript date components.
    # EventKit returns NSDate objects, so handle both NSDate and Python datetime.
    if hasattr(start_date, "timeIntervalSince1970"):
        # NSDate — convert to naive local datetime
        timestamp = start_date.timeIntervalSince1970()
        start_date = datetime.fromtimestamp(timestamp)
    elif hasattr(start_date, "tzinfo") and start_date.tzinfo is not None:
        start_date = start_date.astimezone().replace(tzinfo=None)

    applescript = f'''
    tell application "Calendar"
        set targetDate to current date
        set year of targetDate to {start_date.year}
        set month of targetDate to {start_date.month}
        set day of targetDate to {start_date.day}
        set hours of targetDate to {start_date.hour}
        set minutes of targetDate to {start_date.minute}
        set seconds of targetDate to {start_date.second}

        -- Step 1: Find the event (retry if Calendar.app hasn't synced it yet)
        set maxFindAttempts to 5
        set foundEvent to missing value

        repeat maxFindAttempts times
            try
                set cal to first calendar whose name is "{escaped_calendar}"
                set matchingEvents to (every event of cal whose summary is "{escaped_title}" and start date is targetDate)
                if (count of matchingEvents) > 0 then
                    set foundEvent to item 1 of matchingEvents
                    exit repeat
                end if
            end try
            delay 2
        end repeat

        if foundEvent is missing value then
            error "Event not found after " & maxFindAttempts & " attempts for \\"{escaped_title}\\" in \\"{escaped_calendar}\\""
        end if

        -- Step 2: Add attendees (once only)
        tell foundEvent
            repeat with attendeeData in {{{attendees_list}}}
                make new attendee with properties attendeeData
            end repeat
        end tell

        -- Step 3: Verify attendees persisted (retry read, not write)
        set maxVerifyAttempts to 3
        repeat maxVerifyAttempts times
            delay 2
            if (count of (every attendee of foundEvent)) > 0 then
                return "success"
            end if
        end repeat

        error "Attendees added but did not persist for \\"{escaped_title}\\" in \\"{escaped_calendar}\\""
    end tell
    '''

    try:
        result = subprocess.run(
            ["osascript", "-e", applescript],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            logger.warning(f"Failed to add attendees via AppleScript: {result.stderr}")
        else:
            logger.info(f"Successfully added {len(attendee_emails)} attendee(s) via AppleScript")
    except Exception as e:
        logger.warning(f"Exception adding attendees via AppleScript: {e}")


class CalendarManager:
    def __init__(self):
        self.event_store = EKEventStore.alloc().init()

        # Force a fresh permission check
        auth_status = EKEventStore.authorizationStatusForEntityType_(EKEntityTypeEvent)
        logger.debug(f"Initial Calendar authorization status: {auth_status}")

        # Always request access regardless of current status
        if not self._request_access():
            logger.error("Calendar access request failed")
            raise ValueError(
                "Calendar access not granted. Please check System Settings > Privacy & Security > Calendar."
            )
        logger.info("Calendar access granted successfully")

    def list_events(
        self,
        start_time: datetime,
        end_time: datetime,
        calendar_name: str | None = None,
    ) -> list[Event]:
        """List all events within a given date range

        Args:
            start_time: The start time of the date range
            end_time: The end time of the date range
            calendar_name: The name of the calendar to filter by

        Returns:
            list[Event]: A list of events within the date range
        """
        # only list events in a particular calendar if specified, otherwise search across all calendars
        calendar = self._find_calendar_by_name(calendar_name) if calendar_name else None
        if calendar_name and not calendar:
            raise NoSuchCalendarException(calendar_name)

        calendars = [calendar] if calendar else None

        logger.info(
            f"Listing events between {start_time} - {end_time}, searching in: {calendar_name if calendar_name else 'all calendars'}"
        )

        # Convert timezone-aware datetimes to naive local time for EventKit
        # This allows Claude to provide times in any timezone and we'll convert correctly
        start_naive = to_eventkit_datetime(start_time)
        end_naive = to_eventkit_datetime(end_time)

        predicate = self.event_store.predicateForEventsWithStartDate_endDate_calendars_(start_naive, end_naive, calendars)

        events = self.event_store.eventsMatchingPredicate_(predicate)
        return [Event.from_ekevent(event) for event in events]

    def create_event(self, new_event: CreateEventRequest) -> Event:
        """Create a new calendar event

        Args:
            new_event: The event to create

        Returns:
            Event | None: The created event with identifier if successful, None if failed
        """
        ekevent = EKEvent.eventWithEventStore_(self.event_store)

        ekevent.setTitle_(new_event.title)
        # Convert timezone-aware datetimes to naive local time for EventKit
        ekevent.setStartDate_(to_eventkit_datetime(new_event.start_time))
        ekevent.setEndDate_(to_eventkit_datetime(new_event.end_time))

        if new_event.notes:
            ekevent.setNotes_(new_event.notes)
        if new_event.location:
            ekevent.setLocation_(new_event.location)
        if new_event.url:
            ekevent.setURL_(new_event.url)
        if new_event.all_day:
            ekevent.setAllDay_(new_event.all_day)

        if new_event.alarms_minutes_offsets:
            for minutes in new_event.alarms_minutes_offsets:
                # actual_minutes = minutes + (9 * 60) if new_event.all_day else minutes
                alarm = EKAlarm.alarmWithRelativeOffset_(-60 * minutes)
                ekevent.addAlarm_(alarm)

        if new_event.recurrence_rule:
            ekevent.setRecurrenceRule_(new_event.recurrence_rule.to_ek_recurrence())

        if new_event.calendar_name:
            calendar = self._find_calendar_by_name(new_event.calendar_name)
            if not calendar:
                logger.error(
                    f"Failed to create event: The specified calendar '{new_event.calendar_name}' does not exist."
                )
                raise NoSuchCalendarException(new_event.calendar_name)
        else:
            calendar = self.event_store.defaultCalendarForNewEvents()
            logger.debug(f"Using default calendar, {calendar}, for new event")

        ekevent.setCalendar_(calendar)

        try:
            success, error = self.event_store.saveEvent_span_error_(ekevent, EKSpanThisEvent, None)

            if not success:
                logger.error(f"Failed to save event: {error}")
                raise Exception(error)

            logger.info(f"Successfully created event: {new_event.title}")

            # Add attendees via AppleScript after event is saved
            # EventKit doesn't support adding attendees programmatically, but Calendar.app's
            # AppleScript interface does
            if new_event.attendees:
                try:
                    add_attendees_via_applescript(
                        attendee_emails=new_event.attendees,
                        event_title=new_event.title,
                        calendar_name=ekevent.calendar().title(),
                        start_date=ekevent.startDate(),
                    )
                    # Refresh store so the returned Event includes attendees
                    self.event_store.refreshSourcesIfNecessary()
                except Exception as e:
                    logger.warning(f"Failed to add attendees via AppleScript: {e}")

            return Event.from_ekevent(ekevent)

        except Exception as e:
            logger.exception(e)
            raise

    def update_event(
        self,
        event_id: str,
        request: UpdateEventRequest,
        update_future_events: bool = False,
        occurrence_date: datetime | None = None,
    ) -> Event:
        """Update an existing event or a specific occurrence of a recurring event.

        Args:
            event_id: The unique identifier of the event to update
            request: The update request containing the fields to modify
            update_future_events: When True with occurrence_date, updates this occurrence and all future ones.
                                 When False (default) with occurrence_date, updates only this specific occurrence.
                                 Ignored when occurrence_date is None.
            occurrence_date: The exact start time of the occurrence to update.
                           If provided, updates only that specific occurrence.
                           If None, updates all occurrences (existing behavior).

        Returns:
            Event: The updated event if successful

        Raises:
            NoSuchEventException: If the event or occurrence is not found
            NoSuchCalendarException: If the requested calendar doesn't exist
        """
        # If updating a specific occurrence, find it; otherwise find the master event
        if occurrence_date:
            existing_event = self.find_event_occurrence(event_id, occurrence_date)
            if not existing_event:
                raise NoSuchEventException(
                    f"{event_id} at {occurrence_date.isoformat()} - occurrence not found"
                )
            logger.info(f"Found occurrence for update at {occurrence_date.isoformat()}")
        else:
            existing_event = self.find_event_by_id(event_id)
            if not existing_event:
                raise NoSuchEventException(event_id)

        existing_ek_event = existing_event._raw_event
        if not existing_ek_event:
            raise NoSuchEventException(event_id)

        if request.title is not None:
            existing_ek_event.setTitle_(request.title)
        if request.start_time is not None:
            # Convert timezone-aware datetime to naive local time for EventKit
            existing_ek_event.setStartDate_(to_eventkit_datetime(request.start_time))
        if request.end_time is not None:
            # Convert timezone-aware datetime to naive local time for EventKit
            existing_ek_event.setEndDate_(to_eventkit_datetime(request.end_time))
        if request.location is not None:
            existing_ek_event.setLocation_(request.location)
        if request.notes is not None:
            existing_ek_event.setNotes_(request.notes)
        if request.url is not None:
            existing_ek_event.setURL_(request.url)
        if request.all_day is not None:
            existing_ek_event.setAllDay_(request.all_day)

        # Update calendar if specified
        if request.calendar_name:
            calendar = self._find_calendar_by_name(request.calendar_name)
            if calendar:
                existing_ek_event.setCalendar_(calendar)
            else:
                raise NoSuchCalendarException(request.calendar_name)

        # Update recurrence rule
        if request.recurrence_rule is not None:
            existing_ek_event.setRecurrenceRule_(request.recurrence_rule.to_ek_recurrence())

        # Update alarms if specified
        if request.alarms_minutes_offsets is not None:
            alarms = []
            for minutes in request.alarms_minutes_offsets:
                # For all-day events EK considers start of day as reference point for alarms, so subtract one day
                actual_minutes = minutes - 1440 if request.all_day else minutes
                alarm = EKAlarm.alarmWithRelativeOffset_(-60 * actual_minutes)  # Convert to seconds
                alarms.append(alarm)
            existing_ek_event.setAlarms_(alarms)

        try:
            # Determine the correct span based on parameters
            # - If occurrence_date is provided and update_future_events is True: update this and all future
            # - If occurrence_date is provided and update_future_events is False: update only this one
            # - If occurrence_date is None: update all occurrences (backward compatibility)
            if occurrence_date and update_future_events:
                span = EKSpanFutureEvents  # This occurrence and all future ones
            elif occurrence_date:
                span = EKSpanThisEvent  # Only this specific occurrence
            else:
                span = EKSpanFutureEvents  # All occurrences (maintains backward compatibility)

            success, error = self.event_store.saveEvent_span_error_(existing_ek_event, span, None)

            if not success:
                logger.error(f"Failed to update event: {error}")
                raise Exception(error)

            # Update attendees via AppleScript after event is saved
            # EventKit doesn't support modifying attendees programmatically, but Calendar.app's
            # AppleScript interface does
            if request.attendees is not None:
                try:
                    add_attendees_via_applescript(
                        attendee_emails=request.attendees,
                        event_title=request.title if request.title else existing_event.title,
                        calendar_name=existing_ek_event.calendar().title(),
                        start_date=existing_ek_event.startDate(),
                    )
                    # Refresh store so the returned Event includes attendees
                    self.event_store.refreshSourcesIfNecessary()
                except Exception as e:
                    logger.warning(f"Failed to update attendees via AppleScript: {e}")

            # Build log message based on what was updated
            if occurrence_date and update_future_events:
                scope = f"occurrence at {occurrence_date.isoformat()} and all future occurrences"
            elif occurrence_date:
                scope = f"occurrence at {occurrence_date.isoformat()}"
            else:
                scope = "all occurrences"

            logger.info(f"Successfully updated {scope}: {request.title or existing_event.title}")
            return Event.from_ekevent(existing_ek_event)

        except Exception as e:
            logger.error(f"Failed to update event: {e}")
            raise

    def delete_event(
        self, event_id: str, delete_entire_series: bool = False, occurrence_date: datetime | None = None
    ) -> bool:
        """Delete an event by its identifier, optionally targeting a specific occurrence or future events

        Args:
            event_id: The unique identifier of the event to delete
            delete_entire_series: When True with occurrence_date, deletes the occurrence and all future ones.
                                 When True without occurrence_date, deletes all occurrences.
                                 When False (default), deletes only the specific occurrence.
            occurrence_date: Datetime of specific occurrence to target.
                             Required when deleting a specific occurrence of a recurring event.

        Returns:
            bool: True if deletion was successful, False otherwise

        Raises:
            NoSuchEventException: If the event with the given ID doesn't exist
            Exception: If there was an error deleting the event

        Behavior:
            - Non-recurring event: Just use event_id (delete_entire_series is ignored)
            - Delete one occurrence: provide occurrence_date, delete_entire_series=False (default)
            - Delete from occurrence forward: provide occurrence_date, delete_entire_series=True
            - Delete all occurrences: event_id only, delete_entire_series=True
        """
        # If occurrence_date is provided, find the specific occurrence
        if occurrence_date:
            existing_event = self.find_event_occurrence(event_id, occurrence_date)
            if not existing_event:
                raise NoSuchEventException(f"{event_id} at {occurrence_date.isoformat()}")
        else:
            existing_event = self.find_event_by_id(event_id)
            if not existing_event:
                raise NoSuchEventException(event_id)

        existing_ek_event = existing_event._raw_event
        if not existing_ek_event:
            raise NoSuchEventException(event_id)

        try:
            # Use EKSpanFutureEvents to delete all future occurrences, or EKSpanThisEvent for just this one
            span = EKSpanFutureEvents if delete_entire_series else EKSpanThisEvent
            success, error = self.event_store.removeEvent_span_error_(existing_ek_event, span, None)

            if not success:
                logger.error(f"Failed to delete event: {error}")
                raise Exception(error)

            # Build log message based on what was deleted
            if occurrence_date and delete_entire_series:
                scope = f"occurrence at {occurrence_date.isoformat()} and all future occurrences"
            elif occurrence_date:
                scope = f"occurrence at {occurrence_date.isoformat()}"
            elif delete_entire_series:
                scope = "all occurrences"
            else:
                scope = "event"

            logger.info(f"Successfully deleted: {existing_event.title} {scope}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete event: {e}")
            raise

    def find_event_by_id(self, identifier: str) -> Event | None:
        """Find an event by its identifier

        Args:
            identifier: The unique identifier of the event

        Returns:
            Event | None: The event if found, None otherwise
        """
        ekevent = self.event_store.eventWithIdentifier_(identifier)
        if not ekevent:
            logger.info(f"No event found with ID: {identifier}")
            return None

        return Event.from_ekevent(ekevent)

    def find_event_occurrence(self, event_id: str, occurrence_date: datetime) -> Event | None:
        """Find a specific occurrence of a recurring event.

        Searches for events near the occurrence_date and matches by comparing datetimes.
        If the datetime has no timezone, tries both as-provided and UTC interpretations.

        Args:
            event_id: The event identifier
            occurrence_date: Start time of the occurrence

        Returns:
            The matching occurrence, or None if not found
        """
        result = self._search_occurrence_by_datetime(event_id, occurrence_date)
        if result:
            return result

        # If naive datetime, try UTC interpretation (common when Claude constructs local times)
        if occurrence_date.tzinfo is None:
            logger.info(f"No match for {event_id}, trying UTC interpretation of {occurrence_date}")
            utc_datetime = occurrence_date.replace(tzinfo=timezone.utc)
            result = self._search_occurrence_by_datetime(event_id, utc_datetime)
            if result:
                logger.info(f"Found match using UTC interpretation")
                return result

        logger.info(f"No occurrence found for {event_id} at {occurrence_date}")
        return None

    def _search_occurrence_by_datetime(self, event_id: str, target_datetime: datetime) -> Event | None:
        """Search for occurrence by datetime with timezone-aware matching.

        Uses a minimal ±1 minute search window (required by EventKit's predicate API),
        then does timezone-normalized datetime matching.

        Args:
            event_id: The event identifier
            target_datetime: The datetime to match (can be timezone-aware or naive)

        Returns:
            Event if found, None otherwise
        """
        # Convert search window to naive local time for EventKit
        search_start_naive = to_eventkit_datetime(target_datetime - timedelta(minutes=1))
        search_end_naive = to_eventkit_datetime(target_datetime + timedelta(minutes=1))

        predicate = self.event_store.predicateForEventsWithStartDate_endDate_calendars_(
            search_start_naive, search_end_naive, None
        )
        events = self.event_store.eventsMatchingPredicate_(predicate)

        # Convert target to naive local time for matching against EventKit's naive times
        target_naive = to_eventkit_datetime(target_datetime)

        for ekevent in events:
            # EventKit returns naive datetimes in local timezone
            if ekevent.eventIdentifier() == event_id and ekevent.startDate() == target_naive:
                logger.debug(f"Found occurrence for {event_id} at {target_datetime}")
                return Event.from_ekevent(ekevent)

        return None

    def list_calendar_names(self) -> list[str]:
        """List all available calendar names

        Returns:
            list[str]: A list of calendar names
        """
        calendars = self.event_store.calendars()
        return [calendar.title() for calendar in calendars]

    def list_calendars(self) -> list[Any]:
        """List all available calendars

        Returns:
            list[Any]: A list of EK calendar objects
        """
        return self.event_store.calendars()

    def _request_access(self) -> bool:
        """Request access to interact with the MacOS calendar"""
        semaphore = Semaphore(0)
        access_granted = False

        def completion(granted: bool, error) -> None:
            nonlocal access_granted
            access_granted = granted
            semaphore.release()

        self.event_store.requestAccessToEntityType_completion_(0, completion)
        semaphore.acquire()
        return access_granted

    def _find_calendar_by_id(self, calendar_id: str) -> Any | None:
        """Find a calendar by ID. Returns None if not found.

        Args:
            calendar_id: The ID of the calendar to find

        Returns:
            Any | None: The calendar if found, None otherwise
        """

        for calendar in self.event_store.calendars():
            if calendar.uniqueIdentifier() == calendar_id:
                return calendar

        logger.info(f"Calendar '{calendar_id}' not found")
        return None

    def _find_calendar_by_name(self, calendar_name: str) -> Any | None:
        """Find a calendar by name. Returns None if not found.

        Args:
            calendar_name: The name of the calendar to find

        Returns:
            Any | None: The calendar if found, None otherwise
        """

        for calendar in self.event_store.calendars():
            if calendar.title() == calendar_name:
                return calendar

        logger.info(f"Calendar '{calendar_name}' not found")
        return None

    def _create_calendar(self, calendar_name: str, source_name: str = "iCloud") -> Any | None:
        """Create a new calendar with the specified name.

        Args:
            calendar_name: The name for the new calendar
            source_type: The type of source to use (2=Exchange, 4=MobileMe/iCloud, 5=Subscribed).
                        If None, uses the first available source.

        Returns:
            Any | None: The created calendar if successful, None if failed

        Raises:
            Exception: If there was an error creating the calendar or no matching source found
        """
        logger.info(f"Creating new calendar: {calendar_name}")

        # Create new calendar for events
        new_calendar = EKCalendar.calendarForEntityType_eventStore_(EKEntityTypeEvent, self.event_store)
        new_calendar.setTitle_(calendar_name)

        # Set calendar source based on source_type
        sources = self.event_store.sources()
        selected_source = None

        for source in sources:
            if source.title() == source_name and source.supportsCalendarCreation():
                logger.info(f"Using source: {source.title()} (type: {source.sourceType()})")
                selected_source = source
                break

        if not selected_source:
            available_sources = [(s.title(), s.sourceType()) for s in sources if source.supportsCalendarCreation()]
            error_msg = f"No source found matching title {source_name}. Available sources: {available_sources}"
            logger.error(error_msg)
            raise ValueError(error_msg)

        new_calendar.setSource_(selected_source)

        try:
            success, error = self.event_store.saveCalendar_commit_error_(new_calendar, True, None)

            if not success:
                logger.error(f"Failed to create calendar: {error}")
                raise Exception(error)

            logger.info(f"Successfully created calendar: {calendar_name}")
            return new_calendar

        except Exception as e:
            logger.exception(f"Error creating calendar: {e}")
            raise

    def _delete_calendar(self, calendar_id: str) -> bool:
        """Delete a calendar by its name with extra verification."""
        logger.info(f"Attempting to delete calendar with ID: {calendar_id}")

        calendar = self._find_calendar_by_id(calendar_id)
        if not calendar:
            raise NoSuchCalendarException(calendar_id)

        try:
            # Try deletion with explicit commit
            success, error = self.event_store.removeCalendar_commit_error_(calendar, True, None)

            if not success:
                logger.error(f"Failed to delete calendar: {error}")
                raise Exception(error)

            # Verify deletion
            remaining_calendars = self.list_calendar_names()
            if calendar_id in remaining_calendars:
                logger.error(f"Calendar {calendar_id} still exists after deletion!")
                raise Exception(f"Calendar {calendar_id} was not properly deleted")

            logger.info(f"Successfully deleted calendar: {calendar_id}")
            return True

        except Exception as e:
            logger.exception(f"Error deleting calendar: {e}")
            raise


class NoSuchCalendarException(Exception):
    def __init__(self, calendar_name: str):
        super().__init__(f"Calendar: {calendar_name} does not exist")


class NoSuchEventException(Exception):
    def __init__(self, event_id: str):
        super().__init__(f"Event with id: {event_id} does not exist")
