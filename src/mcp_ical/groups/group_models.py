"""Pydantic models for calendar group data structures."""

from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, field_validator, Field, model_validator


class CalendarGroup(BaseModel):
    """Model representing a calendar group with validation."""
    
    name: str = Field(..., min_length=1, max_length=100)
    calendar_ids: List[str] = Field(default_factory=list)
    description: Optional[str] = Field(default="", max_length=500)
    created: datetime = Field(default_factory=datetime.now)
    modified: datetime = Field(default_factory=datetime.now)
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        """Validate group name requirements."""
        if not v or not v.strip():
            raise ValueError("Group name cannot be empty")
        
        # Remove extra whitespace
        v = v.strip()
        
        # Check for invalid characters
        invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
        if any(char in v for char in invalid_chars):
            raise ValueError(f"Group name cannot contain: {', '.join(invalid_chars)}")
        
        return v
    
    @field_validator('calendar_ids')
    @classmethod
    def validate_calendar_ids(cls, v):
        """Validate calendar IDs list."""
        if not isinstance(v, list):
            raise ValueError("calendar_ids must be a list")
        
        # Remove duplicates while preserving order
        seen = set()
        unique_ids = []
        for cal_id in v:
            if cal_id not in seen:
                seen.add(cal_id)
                unique_ids.append(cal_id)
        
        # Validate each calendar ID
        for cal_id in unique_ids:
            if not isinstance(cal_id, str) or not cal_id.strip():
                raise ValueError("All calendar IDs must be non-empty strings")
        
        return unique_ids
    
    @field_validator('description')
    @classmethod
    def validate_description(cls, v):
        """Validate description field."""
        if v is None:
            return ""
        return v.strip()
    
    @model_validator(mode='before')
    @classmethod
    def set_timestamps(cls, values):
        """Set created and modified timestamps."""
        if isinstance(values, dict):
            now = datetime.now()
            # If created is not provided, set it to now
            if 'created' not in values:
                values['created'] = now
            # Only set modified time if not explicitly provided
            if 'modified' not in values:
                values['modified'] = now
        return values
    
    def add_calendar(self, calendar_id: str) -> bool:
        """Add a calendar to the group.
        
        Args:
            calendar_id: ID of calendar to add.
            
        Returns:
            True if added, False if already present.
        """
        if calendar_id not in self.calendar_ids:
            self.calendar_ids.append(calendar_id)
            self.modified = datetime.now()
            return True
        return False
    
    def remove_calendar(self, calendar_id: str) -> bool:
        """Remove a calendar from the group.
        
        Args:
            calendar_id: ID of calendar to remove.
            
        Returns:
            True if removed, False if not present.
        """
        if calendar_id in self.calendar_ids:
            self.calendar_ids.remove(calendar_id)
            self.modified = datetime.now()
            return True
        return False
    
    def update_description(self, description: str) -> None:
        """Update group description.
        
        Args:
            description: New description text.
        """
        self.description = description.strip()
        self.modified = datetime.now()
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "calendar_ids": self.calendar_ids,
            "description": self.description,
            "created": self.created.isoformat(),
            "modified": self.modified.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'CalendarGroup':
        """Create instance from dictionary.
        
        Args:
            data: Dictionary with group data.
            
        Returns:
            CalendarGroup instance.
        """
        # Make a copy to avoid modifying the original
        data = data.copy()
        
        # Handle datetime fields
        if isinstance(data.get('created'), str):
            data['created'] = datetime.fromisoformat(data['created'])
        if isinstance(data.get('modified'), str):
            data['modified'] = datetime.fromisoformat(data['modified'])
        
        return cls(**data)


class GroupsSchema(BaseModel):
    """Schema for the entire groups storage file."""
    
    version: str = Field(default="1.0")
    groups: Dict[str, CalendarGroup] = Field(default_factory=dict)
    
    @field_validator('version')
    @classmethod
    def validate_version(cls, v):
        """Validate schema version format."""
        if not v or not isinstance(v, str):
            raise ValueError("Version must be a non-empty string")
        
        # Basic semantic version validation
        parts = v.split('.')
        if len(parts) < 2:
            raise ValueError("Version must be in format 'major.minor' or 'major.minor.patch'")
        
        try:
            for part in parts:
                int(part)  # Ensure all parts are numeric
        except ValueError:
            raise ValueError("Version parts must be numeric")
        
        return v
    
    @field_validator('groups')
    @classmethod
    def validate_groups(cls, v):
        """Validate groups dictionary."""
        if not isinstance(v, dict):
            raise ValueError("Groups must be a dictionary")
        
        # Validate that keys match group names
        for key, group in v.items():
            if isinstance(group, dict):
                # Convert dict to CalendarGroup if needed
                group = CalendarGroup.from_dict(group)
                v[key] = group
            
            if not isinstance(group, CalendarGroup):
                raise ValueError(f"Group '{key}' must be a CalendarGroup instance")
            
            if key != group.name:
                raise ValueError(f"Group key '{key}' must match group name '{group.name}'")
        
        return v
    
    def add_group(self, group: CalendarGroup) -> bool:
        """Add a group to the schema.
        
        Args:
            group: CalendarGroup to add.
            
        Returns:
            True if added, False if name already exists.
        """
        if group.name in self.groups:
            return False
        
        self.groups[group.name] = group
        return True
    
    def remove_group(self, name: str) -> bool:
        """Remove a group from the schema.
        
        Args:
            name: Name of group to remove.
            
        Returns:
            True if removed, False if not found.
        """
        if name in self.groups:
            del self.groups[name]
            return True
        return False
    
    def get_group(self, name: str) -> Optional[CalendarGroup]:
        """Get a group by name.
        
        Args:
            name: Name of group to retrieve.
            
        Returns:
            CalendarGroup instance or None if not found.
        """
        return self.groups.get(name)
    
    def list_groups(self) -> List[CalendarGroup]:
        """Get all groups as a list.
        
        Returns:
            List of all CalendarGroup instances.
        """
        return list(self.groups.values())
    
    def to_json(self) -> str:
        """Convert schema to JSON string.
        
        Returns:
            JSON representation of the schema.
        """
        data = {
            "version": self.version,
            "groups": {
                name: group.to_dict() for name, group in self.groups.items()
            }
        }
        import json
        return json.dumps(data, indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'GroupsSchema':
        """Create schema from JSON string.
        
        Args:
            json_str: JSON string with schema data.
            
        Returns:
            GroupsSchema instance.
        """
        import json
        data = json.loads(json_str)
        
        # Convert group dictionaries to CalendarGroup instances
        if 'groups' in data:
            groups = {}
            for name, group_data in data['groups'].items():
                if isinstance(group_data, dict):
                    groups[name] = CalendarGroup.from_dict(group_data)
                else:
                    groups[name] = group_data
            data['groups'] = groups
        
        return cls(**data)
    
    def to_dict(self) -> Dict:
        """Convert schema to dictionary for storage.
        
        Returns:
            Dictionary representation suitable for JSON storage.
        """
        return {
            "version": self.version,
            "groups": {
                name: group.to_dict() for name, group in self.groups.items()
            }
        }