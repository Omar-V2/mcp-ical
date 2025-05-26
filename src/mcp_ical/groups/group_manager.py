"""Business logic for calendar group CRUD operations."""

from typing import List, Optional, Dict, Any
from datetime import datetime

from .storage import GroupStorage
from .group_models import CalendarGroup, GroupsSchema


class CalendarGroupManager:
    """Manage calendar group operations with persistent storage."""
    
    def __init__(self, storage: Optional[GroupStorage] = None, calendar_manager=None):
        """Initialize group manager with storage backend.
        
        Args:
            storage: GroupStorage instance. If None, creates default instance.
            calendar_manager: CalendarManager instance for validation. Optional.
        """
        self.storage = storage or GroupStorage()
        self.calendar_manager = calendar_manager
        self._schema_cache: Optional[GroupsSchema] = None
    
    def _load_schema(self) -> GroupsSchema:
        """Load groups schema from storage with caching.
        
        Returns:
            GroupsSchema instance with current data.
        """
        if self._schema_cache is None:
            data = self.storage.load_groups()
            self._schema_cache = GroupsSchema(**data)
        return self._schema_cache
    
    def _save_schema(self, schema: GroupsSchema) -> None:
        """Save schema to storage and update cache.
        
        Args:
            schema: GroupsSchema to save.
        """
        self.storage.save_groups(schema.to_dict())
        self._schema_cache = schema
    
    def _invalidate_cache(self) -> None:
        """Invalidate the schema cache."""
        self._schema_cache = None
    
    def create_group(self, name: str, calendar_ids: List[str] = None, description: str = "") -> CalendarGroup:
        """Create a new calendar group.
        
        Args:
            name: Name of the group (must be unique).
            calendar_ids: List of calendar IDs to include.
            description: Optional description.
            
        Returns:
            Created CalendarGroup instance.
            
        Raises:
            ValueError: If group name already exists or is invalid.
        """
        if calendar_ids is None:
            calendar_ids = []
        
        schema = self._load_schema()
        
        # Check if group already exists
        if name in schema.groups:
            raise ValueError(f"Group '{name}' already exists")
        
        # Create new group
        group = CalendarGroup(
            name=name,
            calendar_ids=calendar_ids,
            description=description
        )
        
        # Add to schema and save
        schema.add_group(group)
        self._save_schema(schema)
        
        return group
    
    def update_group(self, name: str, updates: Dict[str, Any]) -> CalendarGroup:
        """Update an existing calendar group.
        
        Args:
            name: Name of the group to update.
            updates: Dictionary with fields to update.
                   Supported keys: 'calendar_ids', 'description'
                   
        Returns:
            Updated CalendarGroup instance.
            
        Raises:
            ValueError: If group doesn't exist or updates are invalid.
        """
        schema = self._load_schema()
        
        # Check if group exists
        if name not in schema.groups:
            raise ValueError(f"Group '{name}' not found")
        
        group = schema.groups[name]
        
        # Apply updates
        if 'calendar_ids' in updates:
            group.calendar_ids = updates['calendar_ids']
        
        if 'description' in updates:
            group.update_description(updates['description'])
        
        # Update modified time
        group.modified = datetime.now()
        
        # Save changes
        self._save_schema(schema)
        
        return group
    
    def delete_group(self, name: str) -> bool:
        """Delete a calendar group.
        
        Args:
            name: Name of the group to delete.
            
        Returns:
            True if group was deleted, False if not found.
        """
        schema = self._load_schema()
        
        if schema.remove_group(name):
            self._save_schema(schema)
            return True
        
        return False
    
    def get_group(self, name: str) -> Optional[CalendarGroup]:
        """Get a calendar group by name.
        
        Args:
            name: Name of the group to retrieve.
            
        Returns:
            CalendarGroup instance or None if not found.
        """
        schema = self._load_schema()
        return schema.get_group(name)
    
    def list_groups(self) -> List[CalendarGroup]:
        """Get all calendar groups.
        
        Returns:
            List of CalendarGroup instances sorted by name.
        """
        schema = self._load_schema()
        groups = schema.list_groups()
        return sorted(groups, key=lambda g: g.name.lower())
    
    def add_calendar_to_group(self, group_name: str, calendar_id: str) -> bool:
        """Add a calendar to an existing group.
        
        Args:
            group_name: Name of the group.
            calendar_id: ID of calendar to add.
            
        Returns:
            True if calendar was added, False if already present.
            
        Raises:
            ValueError: If group doesn't exist.
        """
        schema = self._load_schema()
        
        if group_name not in schema.groups:
            raise ValueError(f"Group '{group_name}' not found")
        
        group = schema.groups[group_name]
        result = group.add_calendar(calendar_id)
        
        if result:
            self._save_schema(schema)
        
        return result
    
    def remove_calendar_from_group(self, group_name: str, calendar_id: str) -> bool:
        """Remove a calendar from a group.
        
        Args:
            group_name: Name of the group.
            calendar_id: ID of calendar to remove.
            
        Returns:
            True if calendar was removed, False if not present.
            
        Raises:
            ValueError: If group doesn't exist.
        """
        schema = self._load_schema()
        
        if group_name not in schema.groups:
            raise ValueError(f"Group '{group_name}' not found")
        
        group = schema.groups[group_name]
        result = group.remove_calendar(calendar_id)
        
        if result:
            self._save_schema(schema)
        
        return result
    
    def get_calendars_in_group(self, group_name: str) -> List[str]:
        """Get list of calendar IDs in a group.
        
        Args:
            group_name: Name of the group.
            
        Returns:
            List of calendar IDs.
            
        Raises:
            ValueError: If group doesn't exist.
        """
        group = self.get_group(group_name)
        if group is None:
            raise ValueError(f"Group '{group_name}' not found")
        
        return group.calendar_ids.copy()
    
    def validate_calendar_exists(self, calendar_id: str) -> bool:
        """Validate that a calendar ID exists.
        
        Args:
            calendar_id: ID of calendar to validate.
            
        Returns:
            True if calendar exists, False otherwise.
        """
        if not isinstance(calendar_id, str) or not calendar_id.strip():
            return False
        
        # If calendar manager is available, use it for real validation
        if self.calendar_manager is not None:
            calendar = self.calendar_manager._find_calendar_by_id(calendar_id)
            return calendar is not None
        
        # Fallback: basic string validation only
        return True
    
    def get_groups_containing_calendar(self, calendar_id: str) -> List[CalendarGroup]:
        """Get all groups that contain a specific calendar.
        
        Args:
            calendar_id: ID of calendar to search for.
            
        Returns:
            List of CalendarGroup instances containing the calendar.
        """
        groups = self.list_groups()
        return [group for group in groups if calendar_id in group.calendar_ids]
    
    def rename_group(self, old_name: str, new_name: str) -> CalendarGroup:
        """Rename a calendar group.
        
        Args:
            old_name: Current name of the group.
            new_name: New name for the group.
            
        Returns:
            Updated CalendarGroup instance.
            
        Raises:
            ValueError: If old group doesn't exist or new name already exists.
        """
        schema = self._load_schema()
        
        # Check if old group exists
        if old_name not in schema.groups:
            raise ValueError(f"Group '{old_name}' not found")
        
        # Check if new name already exists
        if new_name in schema.groups:
            raise ValueError(f"Group '{new_name}' already exists")
        
        # Get the group and update its name
        group = schema.groups[old_name]
        group.name = new_name
        group.modified = datetime.now()
        
        # Update the schema dictionary
        schema.groups[new_name] = group
        del schema.groups[old_name]
        
        # Save changes
        self._save_schema(schema)
        
        return group
    
    def get_group_stats(self) -> Dict[str, Any]:
        """Get statistics about groups.
        
        Returns:
            Dictionary with group statistics.
        """
        groups = self.list_groups()
        
        if not groups:
            return {
                "total_groups": 0,
                "total_calendars": 0,
                "average_calendars_per_group": 0,
                "largest_group": None,
                "smallest_group": None,
            }
        
        calendar_counts = [len(group.calendar_ids) for group in groups]
        largest_group = max(groups, key=lambda g: len(g.calendar_ids))
        smallest_group = min(groups, key=lambda g: len(g.calendar_ids))
        
        # Count unique calendars across all groups
        all_calendars = set()
        for group in groups:
            all_calendars.update(group.calendar_ids)
        
        return {
            "total_groups": len(groups),
            "total_calendars": len(all_calendars),
            "average_calendars_per_group": sum(calendar_counts) / len(calendar_counts),
            "largest_group": {
                "name": largest_group.name,
                "calendar_count": len(largest_group.calendar_ids)
            },
            "smallest_group": {
                "name": smallest_group.name,
                "calendar_count": len(smallest_group.calendar_ids)
            },
        }
    
    def refresh_from_storage(self) -> None:
        """Refresh data from storage, discarding cache.
        
        Useful when external processes might have modified the storage.
        """
        self._invalidate_cache()
    
    def backup_groups(self) -> str:
        """Create a backup of the current groups.
        
        Returns:
            Path to the backup file.
        """
        return self.storage.backup_file()