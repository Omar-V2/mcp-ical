import sys
from datetime import datetime
from functools import lru_cache
from textwrap import dedent

from loguru import logger
from mcp.server.fastmcp import FastMCP

from .ical import CalendarManager
from .models import CreateEventRequest, UpdateEventRequest
from .groups.group_tools import register_group_tools

mcp = FastMCP("Calendar")

logger.remove()
logger.add(
    sys.stderr,
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
    level="DEBUG",
)


# Initialize the CalendarManager on demand in order to only request calendar permission
# when a calendar tool is invoked instead of on the launch of the Claude Desktop app.
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
    """Get structured calendar information as JSON for use by other tools."""
    import json
    
    try:
        manager = get_calendar_manager()
        calendars = manager.list_calendars()  # Get raw EKCalendar objects
        default_calendar = manager.event_store.defaultCalendarForNewEvents()
        default_id = default_calendar.uniqueIdentifier() if default_calendar else None
        
        calendar_data = []
        
        for cal in calendars:
            source = cal.source()
            source_type = source.sourceType() if source else None
            
            # Map source types to readable names
            source_type_names = {
                0: "Local",
                1: "Exchange", 
                2: "CalDAV",
                3: "MobileMe",
                4: "Subscribed",
                5: "Birthdays"
            }
            
            calendar_info = {
                "name": cal.title(),
                "id": cal.uniqueIdentifier(),
                "source_name": source.title() if source else "Unknown Source",
                "source_type": source_type,
                "source_type_name": source_type_names.get(source_type, f"Unknown ({source_type})"),
                "is_default": cal.uniqueIdentifier() == default_id,
                "is_editable": cal.allowsContentModifications(),
                "supports_events": cal.supportedEventAvailabilities() > 0,
                "is_subscribed": source_type == 4 if source_type is not None else False,
                "is_team_calendar": source_type == 1 if source_type is not None else False,
                "is_birthdays": source_type == 5 if source_type is not None else False
            }
            
            calendar_data.append(calendar_info)
        
        return json.dumps({
            "calendars": calendar_data,
            "total_count": len(calendar_data)
        }, indent=2)
        
    except ValueError as e:
        return json.dumps({"error": str(e)})
    except Exception as e:
        return json.dumps({"error": f"Error listing calendars: {str(e)}"})



@mcp.resource("groups://list")
def get_calendar_groups() -> str:
    """Get structured calendar group information as JSON for use by other tools."""
    import json
    
    try:
        from .groups.group_manager import CalendarGroupManager
        from .groups.calendar_integration import GroupCalendarBridge
        
        calendar_manager = get_calendar_manager()
        group_manager = CalendarGroupManager()
        bridge = GroupCalendarBridge(calendar_manager, group_manager)
        
        groups = group_manager.list_groups()
        
        group_data = []
        for group in groups:
            try:
                # Get calendar names for this group
                calendar_names = bridge.resolve_calendar_ids_to_names(group.calendar_ids)
                
                group_info = {
                    "name": group.name,
                    "description": group.description,
                    "calendar_count": len(group.calendar_ids),
                    "calendar_names": calendar_names,
                    "calendar_ids": group.calendar_ids,
                    "created": group.created.isoformat(),
                    "modified": group.modified.isoformat()
                }
                
                group_data.append(group_info)
                
            except Exception as e:
                # Handle individual group errors gracefully
                group_info = {
                    "name": group.name,
                    "description": group.description,
                    "calendar_count": len(group.calendar_ids),
                    "calendar_names": [],
                    "calendar_ids": group.calendar_ids,
                    "created": group.created.isoformat(),
                    "modified": group.modified.isoformat(),
                    "error": f"Error resolving calendars: {str(e)}"
                }
                group_data.append(group_info)
        
        return json.dumps({
            "groups": group_data,
            "total_count": len(group_data)
        }, indent=2)
        
    except Exception as e:
        return json.dumps({"error": f"Error listing groups: {str(e)}"})


@mcp.tool()
async def list_calendars() -> str:
    """List all available calendars with their properties and account information.
    
    When displaying calendars to the user, format them nicely and include:
    - Calendar name and account/source
    - Type indicators (default, team, subscribed, birthdays, CalDAV, etc.)
    - Access permissions (read-only vs editable)
    - Group calendars by account/source for better organization
    - Use appropriate emojis and formatting for visual clarity
    
    The raw data includes calendar names, source information, types, and permissions."""
    try:
        manager = get_calendar_manager()
        calendars = manager.list_calendars()  # Get raw EKCalendar objects
        default_calendar = manager.event_store.defaultCalendarForNewEvents()
        default_id = default_calendar.uniqueIdentifier() if default_calendar else None
        
        if not calendars:
            return "No calendars found"

        # Group by source and collect detailed info
        grouped = {}
        for cal in calendars:
            source = cal.source()
            source_name = source.title() if source else "Unknown Source"
            
            if source_name not in grouped:
                grouped[source_name] = []
            
            # Determine calendar type and properties
            source_type = source.sourceType() if source else None
            properties = []
            
            if cal.uniqueIdentifier() == default_id:
                properties.append("default")
            
            if source_type == 1:  # Exchange
                properties.append("team")
            elif source_type == 4:  # Subscribed
                properties.append("subscribed")
            elif source_type == 5:  # Birthdays
                properties.append("birthdays")
            elif source_type == 2:  # CalDAV
                properties.append("CalDAV")
            
            if not cal.allowsContentModifications():
                properties.append("read-only")
            else:
                properties.append("editable")
            
            calendar_info = {
                "name": cal.title(),
                "id": cal.uniqueIdentifier(),
                "properties": properties,
                "source_type": source_type
            }
            
            grouped[source_name].append(calendar_info)
        
        # Build result string with calendar data
        result = f"Found {len(calendars)} calendars across {len(grouped)} accounts:\n\n"
        
        for source_name, calendar_list in grouped.items():
            result += f"Account: {source_name}\n"
            for cal_info in calendar_list:
                properties_text = ", ".join(cal_info["properties"])
                result += f"  - {cal_info['name']} ({properties_text})\n"
            result += "\n"
        
        return result.rstrip()

    except Exception as e:
        return f"Error listing calendars: {str(e)}"


@mcp.tool()
async def list_events(start_date: datetime, end_date: datetime, calendar_name: str | None = None) -> str:
    """List calendar events in a date range.

    The start_date should always use the time such that it represents the beginning of that day (00:00:00).
    The end_date should always use the time such that it represents the end of that day (23:59:59).
    This way, range based searches are always inclusive and can locate all events in that date range.

    IMPORTANT: Display the output exactly as returned without reformatting. 
    The output is already formatted for optimal readability.
    Do not translate, summarize, or reformat the response.

    Args:
        start_date: Start date in ISO8601 format (YYYY-MM-DDT00:00:00).
        end_date: Optional end date in ISO8601 format (YYYY-MM-DDT23:59:59).
        calendar_name: Optional calendar name to filter by
    """
    try:
        manager = get_calendar_manager()
        events = manager.list_events(start_date, end_date, calendar_name)
        if not events:
            return "No events found in the specified date range"

        return "".join([str(event) for event in events])

    except Exception as e:
        return f"Error listing events: {str(e)}"


@mcp.tool()
async def create_event(create_event_request: CreateEventRequest) -> str:
    """Create a new calendar event.

    Before using this tool, make sure to:
    1. Ask the user which calendar they want to use if not specified (check calendars://list)
    2. Ask if they want to add a location if none provided
    3. Ask if they want to add any notes/description if none provided
    4. Confirm the date and time with the user
    5. Ask if they want to set reminders for the event

    Args:
        title: Event title
        start_time: Start time in ISO format (YYYY-MM-DDTHH:MM:SS)
        end_time: End time in ISO format (YYYY-MM-DDTHH:MM:SS)
        notes: Optional event notes/description. Ask user if they want to add notes.
        location: Optional event location. Ask user if they want to specify a location.
        calendar_name: Optional calendar name. Ask user which calendar to use, referencing calendars://list.
        all_day: Whether this is an all-day event
        reminder_offsets: List of minutes before the event to trigger reminders\
            e.g. [60, 1440] means two reminders, the first 24 hours before the event and the second one hour before.
        recurrence_rule: Optional recurrence rule for the event. This should be an instance of `RecurrenceRule` with the following fields:
            - frequency: Frequency of the recurrence (e.g., DAILY, WEEKLY, MONTHLY, YEARLY).
            - interval: Interval between recurrences (e.g., every 2 weeks).
            - end_date: Optional end date for the recurrence. If specified, the recurrence will stop on this date.
            - occurrence_count: Optional number of occurrences. If specified, the recurrence will stop after this many occurrences.
            - days_of_week: Optional list of weekdays for the event. Use integers to represent days:
                - Sunday: 1
                - Monday: 2
                - Tuesday: 3
                - Wednesday: 4
                - Thursday: 5
                - Friday: 6
                - Saturday: 7

    Note: Both `end_date` and `occurrence_count` should not be set simultaneously; choose one or the other, or leave both unset.
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
async def update_event(event_id: str, update_event_request: UpdateEventRequest) -> str:
    """Update an existing calendar event.

    Before using this tool, make sure to:
    1. Ask the user which fields they want to update
    2. If moving to a different calendar, verify the calendar exists using calendars://list
    3. If updating time, confirm the new time with the user
    4. Ask if they want to add/update location if not specified
    5. Ask if they want to add/update notes if not specified
    6. Ask if they want to set reminders for the event

    Args:
        event_id: Unique identifier of the event to update
        title: Optional new title
        start_time: Optional new start time in ISO format
        end_time: Optional new end time in ISO format
        notes: Optional new notes/description. Ask user if they want to update notes.
        location: Optional new location. Ask user if they want to specify/update location.
        calendar_name: Optional new calendar. Ask user which calendar to use, referencing calendars://list.
        all_day: Optional all-day flag
        reminder_offsets: List of minutes before the event to trigger reminders\
            e.g. [60, 1440] means two reminders, the first 24 hours before the event and the second one hour before.
        recurrence_rule: Optional recurrence rule for the event. This should be an instance of `RecurrenceRule` with the following fields:
            - frequency: Frequency of the recurrence (e.g., DAILY, WEEKLY, MONTHLY, YEARLY).
            - interval: Interval between recurrences (e.g., every 2 weeks).
            - end_date: Optional end date for the recurrence. If specified, the recurrence will stop on this date.
            - occurrence_count: Optional number of occurrences. If specified, the recurrence will stop after this many occurrences.
            - days_of_week: Optional list of weekdays for the event. Use integers to represent days:
                - Sunday: 1
                - Monday: 2
                - Tuesday: 3
                - Wednesday: 4
                - Thursday: 5
                - Friday: 6
                - Saturday: 7

    Note: Both `end_date` and `occurrence_count` should not be set simultaneously; choose one or the other, or leave both unset.
    """
    try:
        manager = get_calendar_manager()
        event = manager.update_event(event_id, update_event_request)
        if not event:
            return f"Failed to update event. Event with ID {event_id} not found or update failed."

        return f"Successfully updated event: {event.title}"

    except Exception as e:
        return f"Error updating event: {str(e)}"


@mcp.tool()
async def delete_event(event_id: str) -> str:
    """Delete an existing calendar event.

    Before using this tool, make sure to:
    1. Confirm with the user that they want to delete the event
    2. For recurring events, note that this will delete all future occurrences

    Args:
        event_id: Unique identifier of the event to delete

    Returns:
        str: Success or error message
    """
    try:
        manager = get_calendar_manager()
        success = manager.delete_event(event_id)
        if not success:
            return f"Failed to delete event with ID {event_id}."

        return f"Successfully deleted event with ID {event_id}"

    except Exception as e:
        return f"Error deleting event: {str(e)}"


def main():
    logger.info("Running mcp-ical server...")
    
    # Register group tools
    register_group_tools(mcp, get_calendar_manager)
    
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
