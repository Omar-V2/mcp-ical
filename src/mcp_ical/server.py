import sys
from datetime import datetime
from functools import lru_cache
from textwrap import dedent

from loguru import logger
from mcp.server.fastmcp import FastMCP

from .ical import CalendarManager
from .models import CreateEventRequest, UpdateEventRequest

mcp = FastMCP("Calendar")

logger.remove()
logger.add(
    sys.stderr,
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
    level="DEBUG",
)


@lru_cache(maxsize=None)
def get_calendar_manager() -> CalendarManager:
    """Get or initialize the calendar manager with proper error handling."""
    try:
        return CalendarManager()
    except ValueError as e:
        error_msg = dedent("""\
        Calendar access is not granted. Please follow these steps:

        1. Open System Preferences/Settings
        2. Go to Privacy & Security > Calendar
        3. Check the box next to your terminal application or Claude Desktop
        4. Restart Claude Desktop

        Once you've granted access, try your calendar operation again.
        """)
        raise ValueError(error_msg) from e


@mcp.resource("calendars://list")
def get_calendars() -> str:
    """List available calendars."""
    try:
        manager = get_calendar_manager()
        calendars = manager.list_calendar_names()
        if not calendars:
            return "No calendars found"
        return "Available calendars:\n" + "\n".join(f"- {cal}" for cal in calendars)
    except ValueError as e:
        return str(e)
    except Exception as e:
        return f"Error listing calendars: {str(e)}"


@mcp.tool()
async def list_calendars() -> str:
    """List all available calendars."""
    try:
        manager = get_calendar_manager()
        calendars = manager.list_calendar_names()
        if not calendars:
            return "No calendars found"

        return "Available calendars:\n" + "\n".join(f"- {calendar}" for calendar in calendars)

    except Exception as e:
        return f"Error listing calendars: {str(e)}"


@mcp.tool()
async def list_events(start_date: datetime, end_date: datetime, calendar_name: str | None = None) -> str:
    """List calendar events in a date range. Returns compact summaries; use get_event for full details.

    Args:
        start_date: ISO8601 start (use T00:00:00 for day start).
        end_date: ISO8601 end (use T23:59:59 for day end).
        calendar_name: Optional calendar name filter.
    """
    try:
        manager = get_calendar_manager()
        events = manager.list_events(start_date, end_date, calendar_name)
        if not events:
            return "No events found in the specified date range"

        return "\n\n".join([event.to_compact_str() for event in events])

    except Exception as e:
        return f"Error listing events: {str(e)}"


@mcp.tool()
async def get_event(event_id: str) -> str:
    """Get full details of an event (complete notes, attendee names, etc).

    Args:
        event_id: Event identifier from list_events output.
    """
    try:
        manager = get_calendar_manager()
        event = manager.find_event_by_id(event_id)
        if not event:
            return f"No event found with ID: {event_id}"
        return str(event)
    except Exception as e:
        return f"Error fetching event: {str(e)}"


@mcp.tool()
async def create_event(create_event_request: CreateEventRequest) -> str:
    """Create a calendar event. Confirm details with user before calling.

    Args:
        create_event_request: Event details (title, start_time, end_time required; calendar_name, location, notes, alarms_minutes_offsets, url, all_day, recurrence_rule optional). Recurrence: set frequency (DAILY/WEEKLY/MONTHLY/YEARLY), interval, and one of end_date or occurrence_count. days_of_week: Sun=1..Sat=7.
    """
    logger.info(f"Incoming Create Event Request: {create_event_request}")
    try:
        manager = get_calendar_manager()

        event = manager.create_event(create_event_request)
        if not event:
            return "Failed to create event. Please check calendar permissions and try again."

        return f"Successfully created event: {event.title} (ID: {event.identifier})"

    except Exception as e:
        return f"Error creating event: {str(e)}"


@mcp.tool()
async def update_event(
    event_id: str,
    update_event_request: UpdateEventRequest,
    update_future_events: bool = False,
    occurrence_date: datetime | None = None,
) -> str:
    """Update a calendar event. For recurring events, use occurrence_date from list_events (local time, no TZ offset).

    Args:
        event_id: Event identifier.
        update_event_request: Fields to update (all optional: title, start_time, end_time, calendar_name, location, notes, alarms_minutes_offsets, url, all_day, recurrence_rule).
        update_future_events: With occurrence_date: True=this+future, False=this only. Without occurrence_date: updates all.
        occurrence_date: Exact start time from list_events, format YYYY-MM-DDTHH:MM:SS (no TZ offset). Required for single-occurrence updates.
    """
    logger.info(
        f"Attempting to update event with ID: {event_id}, "
        f"update_future_events={update_future_events}, "
        f"occurrence_date={occurrence_date}"
    )
    try:
        manager = get_calendar_manager()
        event = manager.update_event(event_id, update_event_request, update_future_events, occurrence_date)
        if not event:
            return f"Failed to update event. Event with ID {event_id} not found or update failed."

        if occurrence_date and update_future_events:
            scope = f"occurrence at {occurrence_date.isoformat()} and all future occurrences"
        elif occurrence_date:
            scope = f"occurrence at {occurrence_date.isoformat()}"
        else:
            scope = "event"

        return f"Successfully updated {scope}: {event.title}"

    except Exception as e:
        return f"Error updating event: {str(e)}"


@mcp.tool()
async def delete_event(
    event_id: str, delete_entire_series: bool = False, occurrence_date: datetime | None = None
) -> str:
    """Delete a calendar event. Confirm with user before calling. For recurring events, use occurrence_date from list_events (local time, no TZ offset).

    Args:
        event_id: Event identifier.
        delete_entire_series: With occurrence_date: True=this+future. Without: True=entire series. False(default)=single occurrence.
        occurrence_date: Exact start time from list_events, format YYYY-MM-DDTHH:MM:SS (no TZ offset). Required for single-occurrence deletes.
    """
    logger.info(
        f"Attempting to delete event with ID: {event_id}, "
        f"delete_entire_series={delete_entire_series}, "
        f"occurrence_date={occurrence_date}"
    )
    try:
        manager = get_calendar_manager()

        success = manager.delete_event(event_id, delete_entire_series, occurrence_date)

        if success:
            return "Event deleted successfully"
        else:
            return f"Failed to delete event with ID {event_id}"

    except Exception as e:
        return f"Error deleting event: {str(e)}"


def main():
    logger.info("Running mcp-ical server...")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
