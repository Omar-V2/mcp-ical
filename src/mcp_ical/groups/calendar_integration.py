"""Bridge between group manager and existing CalendarManager."""

from typing import List, Dict, Any, Optional
from datetime import datetime

from .group_manager import CalendarGroupManager
from ..ical import CalendarManager, NoSuchCalendarException
from ..models import Event


class GroupCalendarBridge:
    """Bridge class for calendar operations using groups."""
    
    def __init__(self, calendar_manager: CalendarManager, group_manager: Optional[CalendarGroupManager] = None):
        """Initialize the bridge with calendar and group managers.
        
        Args:
            calendar_manager: CalendarManager instance for calendar operations.
            group_manager: CalendarGroupManager instance. If None, creates default instance.
        """
        self.calendar_manager = calendar_manager
        self.group_manager = group_manager or CalendarGroupManager(calendar_manager=calendar_manager)
    
    def get_events_by_group(self, group_name: str, start_date: datetime, end_date: datetime) -> List[Event]:
        """Get all events from calendars in a group within a date range.
        
        Args:
            group_name: Name of the group.
            start_date: Start date for event search.
            end_date: End date for event search.
            
        Returns:
            List of Event objects from all calendars in the group.
            
        Raises:
            ValueError: If group doesn't exist.
        """
        group = self.group_manager.get_group(group_name)
        if not group:
            raise ValueError(f"Group '{group_name}' not found")
        
        all_events = []
        
        # Get events from each calendar in the group
        for calendar_id in group.calendar_ids:
            try:
                # Convert calendar ID to name for CalendarManager API
                calendar_name = self._get_calendar_name_by_id(calendar_id)
                if calendar_name:
                    events = self.calendar_manager.list_events(start_date, end_date, calendar_name)
                    all_events.extend(events)
            except NoSuchCalendarException:
                # Calendar might have been deleted, skip it
                continue
        
        # Sort events by start time
        all_events.sort(key=lambda e: e.start_time)
        return all_events
    
    def validate_group_calendars(self, group_name: str) -> Dict[str, bool]:
        """Validate that all calendars in a group still exist.
        
        Args:
            group_name: Name of the group to validate.
            
        Returns:
            Dictionary mapping calendar IDs to their existence status.
            
        Raises:
            ValueError: If group doesn't exist.
        """
        group = self.group_manager.get_group(group_name)
        if not group:
            raise ValueError(f"Group '{group_name}' not found")
        
        validation_results = {}
        available_calendar_ids = self._get_available_calendar_ids()
        
        for calendar_id in group.calendar_ids:
            validation_results[calendar_id] = calendar_id in available_calendar_ids
        
        return validation_results
    
    def resolve_calendar_names_to_ids(self, calendar_names: List[str]) -> List[str]:
        """Convert calendar names to their corresponding IDs.
        
        Args:
            calendar_names: List of calendar names to resolve.
            
        Returns:
            List of calendar IDs corresponding to the names.
            
        Raises:
            ValueError: If any calendar name doesn't exist.
        """
        calendar_ids = []
        
        for name in calendar_names:
            calendar_id = self._get_calendar_id_by_name(name)
            if calendar_id is None:
                raise ValueError(f"Calendar '{name}' not found")
            calendar_ids.append(calendar_id)
        
        return calendar_ids
    
    def resolve_calendar_ids_to_names(self, calendar_ids: List[str]) -> List[str]:
        """Convert calendar IDs to their corresponding names.
        
        Args:
            calendar_ids: List of calendar IDs to resolve.
            
        Returns:
            List of calendar names corresponding to the IDs.
            
        Raises:
            ValueError: If any calendar ID doesn't exist.
        """
        calendar_names = []
        
        for calendar_id in calendar_ids:
            calendar_name = self._get_calendar_name_by_id(calendar_id)
            if calendar_name is None:
                raise ValueError(f"Calendar with ID '{calendar_id}' not found")
            calendar_names.append(calendar_name)
        
        return calendar_names
    
    def get_calendar_info_for_group(self, group_name: str) -> List[Dict[str, Any]]:
        """Get detailed information about calendars in a group.
        
        Args:
            group_name: Name of the group.
            
        Returns:
            List of dictionaries with calendar information.
            
        Raises:
            ValueError: If group doesn't exist.
        """
        group = self.group_manager.get_group(group_name)
        if not group:
            raise ValueError(f"Group '{group_name}' not found")
        
        calendar_info = []
        
        for calendar_id in group.calendar_ids:
            calendar_name = self._get_calendar_name_by_id(calendar_id)
            calendar_info.append({
                "id": calendar_id,
                "name": calendar_name,
                "exists": calendar_name is not None,
                "group": group_name
            })
        
        return calendar_info
    
    def get_groups_for_calendar(self, calendar_id: str) -> List[str]:
        """Get all groups that contain a specific calendar.
        
        Args:
            calendar_id: ID of the calendar.
            
        Returns:
            List of group names containing the calendar.
        """
        groups = self.group_manager.get_groups_containing_calendar(calendar_id)
        return [group.name for group in groups]
    
    def get_groups_for_calendar_name(self, calendar_name: str) -> List[str]:
        """Get all groups that contain a calendar by name.
        
        Args:
            calendar_name: Name of the calendar.
            
        Returns:
            List of group names containing the calendar.
            
        Raises:
            ValueError: If calendar name doesn't exist.
        """
        calendar_id = self._get_calendar_id_by_name(calendar_name)
        if calendar_id is None:
            raise ValueError(f"Calendar '{calendar_name}' not found")
        
        return self.get_groups_for_calendar(calendar_id)
    
    def create_group_from_calendar_names(self, group_name: str, calendar_names: List[str], description: str = "") -> str:
        """Create a group using calendar names instead of IDs.
        
        Args:
            group_name: Name for the new group.
            calendar_names: List of calendar names to include.
            description: Optional description.
            
        Returns:
            Success message.
            
        Raises:
            ValueError: If any calendar name doesn't exist or group creation fails.
        """
        # Convert names to IDs
        calendar_ids = self.resolve_calendar_names_to_ids(calendar_names)
        
        # Create the group
        group = self.group_manager.create_group(group_name, calendar_ids, description)
        
        return f"Successfully created group '{group_name}' with {len(calendar_ids)} calendars"
    
    def add_calendar_to_group_by_name(self, group_name: str, calendar_name: str) -> bool:
        """Add a calendar to a group using the calendar name.
        
        Args:
            group_name: Name of the group.
            calendar_name: Name of the calendar to add.
            
        Returns:
            True if calendar was added, False if already present.
            
        Raises:
            ValueError: If group or calendar doesn't exist.
        """
        calendar_id = self._get_calendar_id_by_name(calendar_name)
        if calendar_id is None:
            raise ValueError(f"Calendar '{calendar_name}' not found")
        
        return self.group_manager.add_calendar_to_group(group_name, calendar_id)
    
    def remove_calendar_from_group_by_name(self, group_name: str, calendar_name: str) -> bool:
        """Remove a calendar from a group using the calendar name.
        
        Args:
            group_name: Name of the group.
            calendar_name: Name of the calendar to remove.
            
        Returns:
            True if calendar was removed, False if not present.
            
        Raises:
            ValueError: If group doesn't exist.
        """
        calendar_id = self._get_calendar_id_by_name(calendar_name)
        if calendar_id is None:
            # Calendar doesn't exist, but we might still have its ID in the group
            # Try to find it by searching all groups
            groups = self.group_manager.list_groups()
            for group in groups:
                if group.name == group_name:
                    # Find calendar IDs that don't correspond to existing calendars
                    for cal_id in group.calendar_ids:
                        if self._get_calendar_name_by_id(cal_id) is None:
                            # This ID doesn't have a corresponding calendar anymore
                            # Remove it if it might be the one we're looking for
                            return self.group_manager.remove_calendar_from_group(group_name, cal_id)
            raise ValueError(f"Calendar '{calendar_name}' not found")
        
        return self.group_manager.remove_calendar_from_group(group_name, calendar_id)
    
    def cleanup_invalid_calendars(self, group_name: str) -> Dict[str, Any]:
        """Remove invalid calendar IDs from a group.
        
        Args:
            group_name: Name of the group to clean up.
            
        Returns:
            Dictionary with cleanup results.
            
        Raises:
            ValueError: If group doesn't exist.
        """
        group = self.group_manager.get_group(group_name)
        if not group:
            raise ValueError(f"Group '{group_name}' not found")
        
        validation_results = self.validate_group_calendars(group_name)
        invalid_calendar_ids = [cal_id for cal_id, is_valid in validation_results.items() if not is_valid]
        
        removed_count = 0
        for calendar_id in invalid_calendar_ids:
            if self.group_manager.remove_calendar_from_group(group_name, calendar_id):
                removed_count += 1
        
        return {
            "group_name": group_name,
            "removed_count": removed_count,
            "invalid_calendars": invalid_calendar_ids,
            "remaining_calendars": len(group.calendar_ids) - removed_count
        }
    
    def get_available_calendars(self) -> Dict[str, str]:
        """Get all available calendars with their IDs and names.
        
        Returns:
            Dictionary mapping calendar IDs to names.
        """
        calendars = self.calendar_manager.list_calendars()
        return {
            calendar.uniqueIdentifier(): calendar.title()
            for calendar in calendars
        }
    
    def _get_calendar_id_by_name(self, calendar_name: str) -> Optional[str]:
        """Get calendar ID by name.
        
        Args:
            calendar_name: Name of the calendar.
            
        Returns:
            Calendar ID if found, None otherwise.
        """
        calendar = self.calendar_manager._find_calendar_by_name(calendar_name)
        return calendar.uniqueIdentifier() if calendar else None
    
    def _get_calendar_name_by_id(self, calendar_id: str) -> Optional[str]:
        """Get calendar name by ID.
        
        Args:
            calendar_id: ID of the calendar.
            
        Returns:
            Calendar name if found, None otherwise.
        """
        calendar = self.calendar_manager._find_calendar_by_id(calendar_id)
        return calendar.title() if calendar else None
    
    def _get_available_calendar_ids(self) -> set:
        """Get set of all available calendar IDs.
        
        Returns:
            Set of calendar IDs.
        """
        calendars = self.calendar_manager.list_calendars()
        return {calendar.uniqueIdentifier() for calendar in calendars}
    
    def get_group_statistics(self) -> Dict[str, Any]:
        """Get comprehensive statistics about groups and calendar integration.
        
        Returns:
            Dictionary with detailed statistics.
        """
        group_stats = self.group_manager.get_group_stats()
        available_calendars = self.get_available_calendars()
        
        # Count calendars that are in groups vs not in groups
        calendars_in_groups = set()
        for group in self.group_manager.list_groups():
            calendars_in_groups.update(group.calendar_ids)
        
        available_calendar_ids = set(available_calendars.keys())
        ungrouped_calendars = available_calendar_ids - calendars_in_groups
        
        # Count invalid calendar references
        invalid_references = 0
        for group in self.group_manager.list_groups():
            for cal_id in group.calendar_ids:
                if cal_id not in available_calendar_ids:
                    invalid_references += 1
        
        return {
            **group_stats,
            "total_available_calendars": len(available_calendars),
            "calendars_in_groups": len(calendars_in_groups),
            "ungrouped_calendars": len(ungrouped_calendars),
            "invalid_calendar_references": invalid_references,
            "group_coverage_percentage": (len(calendars_in_groups) / len(available_calendars) * 100) if available_calendars else 0
        }