"""MCP server endpoints for group operations."""

from datetime import datetime
from typing import List, Optional
from functools import lru_cache

from mcp.server.fastmcp import FastMCP

from .group_manager import CalendarGroupManager
from .calendar_integration import GroupCalendarBridge
from ..ical import CalendarManager


# Cache for group-related managers
@lru_cache(maxsize=None)
def get_group_manager(calendar_manager=None) -> CalendarGroupManager:
    """Get or initialize the group manager."""
    return CalendarGroupManager(calendar_manager=calendar_manager)


@lru_cache(maxsize=None)
def get_group_bridge(calendar_manager: CalendarManager) -> GroupCalendarBridge:
    """Get or initialize the group calendar bridge."""
    return GroupCalendarBridge(calendar_manager, get_group_manager())


def register_group_tools(mcp: FastMCP, get_calendar_manager_func):
    """Register all group-related MCP tools.
    
    Args:
        mcp: FastMCP instance to register tools with.
        get_calendar_manager_func: Function that returns CalendarManager instance.
    """
    
    @mcp.tool()
    async def create_calendar_group(name: str, calendar_names: List[str], description: str = "") -> str:
        """Create a new calendar group from calendar names.
        
        A calendar group allows you to organize multiple calendars and query them together.
        For example, you could create a "Work" group with your work calendar and team calendars.
        
        Args:
            name: Name for the new group (must be unique)
            calendar_names: List of calendar names to include in the group
            description: Optional description for the group
            
        Returns:
            Success message with group details
        """
        try:
            calendar_manager = get_calendar_manager_func()
            bridge = get_group_bridge(calendar_manager)
            
            result = bridge.create_group_from_calendar_names(name, calendar_names, description)
            return result
            
        except ValueError as e:
            return f"Error creating group: {str(e)}"
        except Exception as e:
            return f"Unexpected error creating group: {str(e)}"
    
    @mcp.tool()
    async def update_calendar_group(group_name: str, calendar_names: List[str] = None, description: str = None) -> str:
        """Update an existing calendar group.
        
        You can update the calendars in a group or change its description.
        
        Args:
            group_name: Name of the group to update
            calendar_names: Optional new list of calendar names (replaces existing calendars)
            description: Optional new description
            
        Returns:
            Success message with updated group details
        """
        try:
            calendar_manager = get_calendar_manager_func()
            bridge = get_group_bridge(calendar_manager)
            group_manager = get_group_manager()
            
            # Build updates dictionary
            updates = {}
            
            if calendar_names is not None:
                # Convert calendar names to IDs
                calendar_ids = bridge.resolve_calendar_names_to_ids(calendar_names)
                updates['calendar_ids'] = calendar_ids
            
            if description is not None:
                updates['description'] = description
            
            if not updates:
                return f"No updates specified for group '{group_name}'"
            
            group = group_manager.update_group(group_name, updates)
            
            calendar_list = bridge.resolve_calendar_ids_to_names(group.calendar_ids)
            return f"Successfully updated group '{group_name}' with {len(calendar_list)} calendars: {', '.join(calendar_list)}"
            
        except ValueError as e:
            return f"Error updating group: {str(e)}"
        except Exception as e:
            return f"Unexpected error updating group: {str(e)}"
    
    @mcp.tool()
    async def delete_calendar_group(group_name: str) -> str:
        """Delete a calendar group.
        
        This only deletes the group, not the calendars themselves.
        
        Args:
            group_name: Name of the group to delete
            
        Returns:
            Success or failure message
        """
        try:
            group_manager = get_group_manager()
            
            if group_manager.delete_group(group_name):
                return f"Successfully deleted group '{group_name}'"
            else:
                return f"Group '{group_name}' not found"
                
        except Exception as e:
            return f"Error deleting group: {str(e)}"
    
    @mcp.tool()
    async def list_calendar_groups() -> str:
        """List all calendar groups with their details.
        
        Shows all groups, their descriptions, and the calendars in each group.
        
        Returns:
            Formatted list of all groups
        """
        try:
            calendar_manager = get_calendar_manager_func()
            bridge = get_group_bridge(calendar_manager)
            group_manager = get_group_manager()
            
            groups = group_manager.list_groups()
            
            if not groups:
                return "No calendar groups found. Use create_calendar_group to create one."
            
            result = "Calendar Groups:\n\n"
            
            for group in groups:
                result += f"📁 **{group.name}**\n"
                if group.description:
                    result += f"   Description: {group.description}\n"
                
                # Get calendar names for display
                try:
                    calendar_names = bridge.resolve_calendar_ids_to_names(group.calendar_ids)
                    if calendar_names:
                        result += f"   Calendars ({len(calendar_names)}): {', '.join(calendar_names)}\n"
                    else:
                        result += "   Calendars: None\n"
                except Exception:
                    # Some calendars might not exist anymore
                    result += f"   Calendar IDs ({len(group.calendar_ids)}): {', '.join(group.calendar_ids)}\n"
                
                result += f"   Created: {group.created.strftime('%Y-%m-%d %H:%M')}\n"
                result += f"   Modified: {group.modified.strftime('%Y-%m-%d %H:%M')}\n\n"
            
            return result
            
        except Exception as e:
            return f"Error listing groups: {str(e)}"
    
    @mcp.tool()
    async def list_calendars_in_group(group_name: str) -> str:
        """List all calendars in a specific group.
        
        Args:
            group_name: Name of the group
            
        Returns:
            List of calendars in the group
        """
        try:
            calendar_manager = get_calendar_manager_func()
            bridge = get_group_bridge(calendar_manager)
            
            calendar_info = bridge.get_calendar_info_for_group(group_name)
            
            if not calendar_info:
                return f"Group '{group_name}' has no calendars"
            
            result = f"Calendars in group '{group_name}':\n\n"
            
            for info in calendar_info:
                status = "✅" if info['exists'] else "❌"
                result += f"{status} {info['name'] or info['id']}"
                if not info['exists']:
                    result += " (calendar no longer exists)"
                result += "\n"
            
            return result
            
        except ValueError as e:
            return f"Error: {str(e)}"
        except Exception as e:
            return f"Unexpected error: {str(e)}"
    
    @mcp.tool()
    async def list_events_by_group(start_date: datetime, end_date: datetime, group_name: str) -> str:
        """List events from all calendars in a group within a date range.
        
        This is useful for getting a unified view of events across multiple related calendars.
        
        Args:
            start_date: Start date in ISO8601 format (YYYY-MM-DDT00:00:00)
            end_date: End date in ISO8601 format (YYYY-MM-DDT23:59:59)
            group_name: Name of the group to query
            
        Returns:
            Formatted list of events from all calendars in the group
        """
        try:
            calendar_manager = get_calendar_manager_func()
            bridge = get_group_bridge(calendar_manager)
            
            events = bridge.get_events_by_group(group_name, start_date, end_date)
            
            if not events:
                return f"No events found in group '{group_name}' for the specified date range"
            
            result = f"Events in group '{group_name}' ({start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}):\n\n"
            
            current_date = None
            for event in events:
                event_date = event.start_time.date()
                if current_date != event_date:
                    current_date = event_date
                    result += f"📅 **{event_date.strftime('%A, %B %d, %Y')}**\n"
                
                time_str = "All Day" if event.all_day else event.start_time.strftime('%H:%M')
                result += f"   • {time_str} - {event.title}"
                if event.calendar_name:
                    result += f" [{event.calendar_name}]"
                if event.location:
                    result += f" @ {event.location}"
                result += "\n"
            
            result += f"\nTotal events: {len(events)}"
            return result
            
        except ValueError as e:
            return f"Error: {str(e)}"
        except Exception as e:
            return f"Unexpected error listing events: {str(e)}"
    
    @mcp.tool()
    async def add_calendar_to_group(group_name: str, calendar_name: str) -> str:
        """Add a calendar to an existing group.
        
        Args:
            group_name: Name of the group
            calendar_name: Name of the calendar to add
            
        Returns:
            Success or failure message
        """
        try:
            calendar_manager = get_calendar_manager_func()
            bridge = get_group_bridge(calendar_manager)
            
            if bridge.add_calendar_to_group_by_name(group_name, calendar_name):
                return f"Successfully added calendar '{calendar_name}' to group '{group_name}'"
            else:
                return f"Calendar '{calendar_name}' is already in group '{group_name}'"
                
        except ValueError as e:
            return f"Error: {str(e)}"
        except Exception as e:
            return f"Unexpected error: {str(e)}"
    
    @mcp.tool()
    async def remove_calendar_from_group(group_name: str, calendar_name: str) -> str:
        """Remove a calendar from a group.
        
        Args:
            group_name: Name of the group
            calendar_name: Name of the calendar to remove
            
        Returns:
            Success or failure message
        """
        try:
            calendar_manager = get_calendar_manager_func()
            bridge = get_group_bridge(calendar_manager)
            
            if bridge.remove_calendar_from_group_by_name(group_name, calendar_name):
                return f"Successfully removed calendar '{calendar_name}' from group '{group_name}'"
            else:
                return f"Calendar '{calendar_name}' was not in group '{group_name}'"
                
        except ValueError as e:
            return f"Error: {str(e)}"
        except Exception as e:
            return f"Unexpected error: {str(e)}"
    
    @mcp.tool()
    async def get_calendar_groups_info() -> str:
        """Get comprehensive information about calendar groups and their status.
        
        Shows statistics about groups, calendar coverage, and any issues.
        
        Returns:
            Detailed information about the groups system
        """
        try:
            calendar_manager = get_calendar_manager_func()
            bridge = get_group_bridge(calendar_manager)
            
            stats = bridge.get_group_statistics()
            
            result = "📊 **Calendar Groups Information**\n\n"
            
            # Basic stats
            result += f"**Groups Overview:**\n"
            result += f"• Total groups: {stats['total_groups']}\n"
            result += f"• Total calendars available: {stats['total_available_calendars']}\n"
            result += f"• Calendars in groups: {stats['calendars_in_groups']}\n"
            result += f"• Ungrouped calendars: {stats['ungrouped_calendars']}\n"
            result += f"• Group coverage: {stats['group_coverage_percentage']:.1f}%\n"
            
            if stats['total_groups'] > 0:
                result += f"• Average calendars per group: {stats['average_calendars_per_group']:.1f}\n"
                
                if stats.get('largest_group'):
                    result += f"• Largest group: '{stats['largest_group']['name']}' ({stats['largest_group']['calendar_count']} calendars)\n"
                
                if stats.get('smallest_group'):
                    result += f"• Smallest group: '{stats['smallest_group']['name']}' ({stats['smallest_group']['calendar_count']} calendars)\n"
            
            # Issues
            if stats['invalid_calendar_references'] > 0:
                result += f"\n⚠️ **Issues Found:**\n"
                result += f"• Invalid calendar references: {stats['invalid_calendar_references']}\n"
                result += "Consider using cleanup tools to remove invalid references.\n"
            
            return result
            
        except Exception as e:
            return f"Error getting groups info: {str(e)}"
    
    @mcp.tool()
    async def cleanup_invalid_calendars_in_group(group_name: str) -> str:
        """Remove invalid calendar references from a group.
        
        This is useful when calendars have been deleted but are still referenced in groups.
        
        Args:
            group_name: Name of the group to clean up
            
        Returns:
            Cleanup results
        """
        try:
            calendar_manager = get_calendar_manager_func()
            bridge = get_group_bridge(calendar_manager)
            
            result_data = bridge.cleanup_invalid_calendars(group_name)
            
            if result_data['removed_count'] == 0:
                return f"Group '{group_name}' has no invalid calendar references"
            
            result = f"🧹 **Cleanup Results for '{group_name}':**\n\n"
            result += f"• Removed {result_data['removed_count']} invalid calendar reference(s)\n"
            result += f"• Remaining calendars: {result_data['remaining_calendars']}\n"
            
            if result_data['invalid_calendars']:
                result += f"• Removed calendar IDs: {', '.join(result_data['invalid_calendars'])}\n"
            
            return result
            
        except ValueError as e:
            return f"Error: {str(e)}"
        except Exception as e:
            return f"Unexpected error during cleanup: {str(e)}"
    
    @mcp.tool()
    async def find_groups_for_calendar(calendar_name: str) -> str:
        """Find all groups that contain a specific calendar.
        
        Args:
            calendar_name: Name of the calendar to search for
            
        Returns:
            List of groups containing the calendar
        """
        try:
            calendar_manager = get_calendar_manager_func()
            bridge = get_group_bridge(calendar_manager)
            
            groups = bridge.get_groups_for_calendar_name(calendar_name)
            
            if not groups:
                return f"Calendar '{calendar_name}' is not in any groups"
            
            result = f"Calendar '{calendar_name}' is in {len(groups)} group(s):\n\n"
            for group_name in groups:
                result += f"• {group_name}\n"
            
            return result
            
        except ValueError as e:
            return f"Error: {str(e)}"
        except Exception as e:
            return f"Unexpected error: {str(e)}"