"""Unit tests for group data models."""

import json
from datetime import datetime
import pytest
from pydantic import ValidationError

from mcp_ical.groups.group_models import CalendarGroup, GroupsSchema


class TestCalendarGroup:
    """Test CalendarGroup model functionality."""
    
    def test_valid_group_creation(self):
        """Test creating a valid calendar group."""
        group = CalendarGroup(
            name="work",
            calendar_ids=["cal1", "cal2"],
            description="Work calendars"
        )
        
        assert group.name == "work"
        assert group.calendar_ids == ["cal1", "cal2"]
        assert group.description == "Work calendars"
        assert isinstance(group.created, datetime)
        assert isinstance(group.modified, datetime)
    
    def test_minimal_group_creation(self):
        """Test creating group with minimal required fields."""
        group = CalendarGroup(name="minimal")
        
        assert group.name == "minimal"
        assert group.calendar_ids == []
        assert group.description == ""
        assert isinstance(group.created, datetime)
        assert isinstance(group.modified, datetime)
    
    def test_name_validation_empty(self):
        """Test validation fails for empty name."""
        with pytest.raises(ValidationError) as exc_info:
            CalendarGroup(name="")
        
        assert "String should have at least 1 character" in str(exc_info.value)
    
    def test_name_validation_whitespace(self):
        """Test name validation strips whitespace."""
        group = CalendarGroup(name="  test  ")
        assert group.name == "test"
    
    def test_name_validation_invalid_chars(self):
        """Test name validation rejects invalid characters."""
        invalid_names = ["test/group", "test\\group", "test:group", "test*group"]
        
        for invalid_name in invalid_names:
            with pytest.raises(ValidationError) as exc_info:
                CalendarGroup(name=invalid_name)
            assert "Group name cannot contain" in str(exc_info.value)
    
    def test_calendar_ids_deduplication(self):
        """Test calendar IDs are deduplicated while preserving order."""
        group = CalendarGroup(
            name="test",
            calendar_ids=["cal1", "cal2", "cal1", "cal3", "cal2"]
        )
        
        assert group.calendar_ids == ["cal1", "cal2", "cal3"]
    
    def test_calendar_ids_validation_invalid_type(self):
        """Test calendar IDs validation rejects invalid types."""
        with pytest.raises(ValidationError) as exc_info:
            CalendarGroup(name="test", calendar_ids="not_a_list")
        
        assert "Input should be a valid list" in str(exc_info.value)
    
    def test_calendar_ids_validation_empty_strings(self):
        """Test calendar IDs validation rejects empty strings."""
        with pytest.raises(ValidationError) as exc_info:
            CalendarGroup(name="test", calendar_ids=["cal1", "", "cal2"])
        
        assert "All calendar IDs must be non-empty strings" in str(exc_info.value)
    
    def test_description_validation_none(self):
        """Test description validation handles None values."""
        group = CalendarGroup(name="test", description=None)
        assert group.description == ""
    
    def test_description_validation_strips_whitespace(self):
        """Test description validation strips whitespace."""
        group = CalendarGroup(name="test", description="  description  ")
        assert group.description == "description"
    
    def test_add_calendar(self):
        """Test adding calendar to group."""
        group = CalendarGroup(name="test", calendar_ids=["cal1"])
        original_modified = group.modified
        
        # Add new calendar
        result = group.add_calendar("cal2")
        assert result is True
        assert "cal2" in group.calendar_ids
        assert group.modified > original_modified
        
        # Try to add duplicate
        result = group.add_calendar("cal1")
        assert result is False
        assert group.calendar_ids.count("cal1") == 1
    
    def test_remove_calendar(self):
        """Test removing calendar from group."""
        group = CalendarGroup(name="test", calendar_ids=["cal1", "cal2"])
        original_modified = group.modified
        
        # Remove existing calendar
        result = group.remove_calendar("cal1")
        assert result is True
        assert "cal1" not in group.calendar_ids
        assert group.modified > original_modified
        
        # Try to remove non-existent calendar
        result = group.remove_calendar("cal3")
        assert result is False
    
    def test_update_description(self):
        """Test updating group description."""
        group = CalendarGroup(name="test", description="old")
        original_modified = group.modified
        
        group.update_description("  new description  ")
        assert group.description == "new description"
        assert group.modified > original_modified
    
    def test_to_dict(self):
        """Test converting group to dictionary."""
        created_time = datetime(2023, 1, 1, 12, 0, 0)
        modified_time = datetime(2023, 1, 2, 12, 0, 0)
        
        group = CalendarGroup(
            name="test",
            calendar_ids=["cal1", "cal2"],
            description="Test group",
            created=created_time,
            modified=modified_time
        )
        
        result = group.to_dict()
        
        assert result["name"] == "test"
        assert result["calendar_ids"] == ["cal1", "cal2"]
        assert result["description"] == "Test group"
        assert result["created"] == "2023-01-01T12:00:00"
        assert result["modified"] == "2023-01-02T12:00:00"
    
    def test_from_dict(self):
        """Test creating group from dictionary."""
        data = {
            "name": "test",
            "calendar_ids": ["cal1", "cal2"],
            "description": "Test group",
            "created": "2023-01-01T12:00:00",
            "modified": "2023-01-02T12:00:00"
        }
        
        group = CalendarGroup.from_dict(data)
        
        assert group.name == "test"
        assert group.calendar_ids == ["cal1", "cal2"]
        assert group.description == "Test group"
        assert group.created == datetime(2023, 1, 1, 12, 0, 0)
        assert group.modified == datetime(2023, 1, 2, 12, 0, 0)
    
    def test_serialization_round_trip(self):
        """Test dictionary serialization round trip."""
        original = CalendarGroup(
            name="test",
            calendar_ids=["cal1", "cal2"],
            description="Test group"
        )
        
        # Convert to dict and back
        data = original.to_dict()
        restored = CalendarGroup.from_dict(data)
        
        assert restored.name == original.name
        assert restored.calendar_ids == original.calendar_ids
        assert restored.description == original.description


class TestGroupsSchema:
    """Test GroupsSchema model functionality."""
    
    def test_empty_schema_creation(self):
        """Test creating empty schema."""
        schema = GroupsSchema()
        
        assert schema.version == "1.0"
        assert schema.groups == {}
    
    def test_schema_with_groups(self):
        """Test creating schema with groups."""
        group1 = CalendarGroup(name="work", calendar_ids=["cal1"])
        group2 = CalendarGroup(name="personal", calendar_ids=["cal2"])
        
        schema = GroupsSchema(
            version="1.1",
            groups={"work": group1, "personal": group2}
        )
        
        assert schema.version == "1.1"
        assert len(schema.groups) == 2
        assert schema.groups["work"] == group1
        assert schema.groups["personal"] == group2
    
    def test_version_validation_empty(self):
        """Test version validation rejects empty strings."""
        with pytest.raises(ValidationError) as exc_info:
            GroupsSchema(version="")
        
        assert "Version must be a non-empty string" in str(exc_info.value)
    
    def test_version_validation_format(self):
        """Test version validation enforces semantic versioning."""
        with pytest.raises(ValidationError) as exc_info:
            GroupsSchema(version="invalid")
        
        assert "Version must be in format" in str(exc_info.value)
        
        with pytest.raises(ValidationError) as exc_info:
            GroupsSchema(version="1.a")
        
        assert "Version parts must be numeric" in str(exc_info.value)
    
    def test_groups_validation_key_mismatch(self):
        """Test groups validation enforces key-name consistency."""
        group = CalendarGroup(name="actual_name")
        
        with pytest.raises(ValidationError) as exc_info:
            GroupsSchema(groups={"wrong_key": group})
        
        assert "Group key 'wrong_key' must match group name 'actual_name'" in str(exc_info.value)
    
    def test_groups_validation_dict_conversion(self):
        """Test groups validation converts dicts to CalendarGroup instances."""
        group_data = {
            "name": "test",
            "calendar_ids": ["cal1"],
            "description": "Test group"
        }
        
        schema = GroupsSchema(groups={"test": group_data})
        
        assert isinstance(schema.groups["test"], CalendarGroup)
        assert schema.groups["test"].name == "test"
    
    def test_add_group(self):
        """Test adding group to schema."""
        schema = GroupsSchema()
        group = CalendarGroup(name="test")
        
        result = schema.add_group(group)
        assert result is True
        assert "test" in schema.groups
        assert schema.groups["test"] == group
        
        # Try to add duplicate
        result = schema.add_group(group)
        assert result is False
    
    def test_remove_group(self):
        """Test removing group from schema."""
        group = CalendarGroup(name="test")
        schema = GroupsSchema(groups={"test": group})
        
        result = schema.remove_group("test")
        assert result is True
        assert "test" not in schema.groups
        
        # Try to remove non-existent group
        result = schema.remove_group("nonexistent")
        assert result is False
    
    def test_get_group(self):
        """Test getting group from schema."""
        group = CalendarGroup(name="test")
        schema = GroupsSchema(groups={"test": group})
        
        result = schema.get_group("test")
        assert result == group
        
        result = schema.get_group("nonexistent")
        assert result is None
    
    def test_list_groups(self):
        """Test listing all groups."""
        group1 = CalendarGroup(name="work")
        group2 = CalendarGroup(name="personal")
        schema = GroupsSchema(groups={"work": group1, "personal": group2})
        
        result = schema.list_groups()
        assert len(result) == 2
        assert group1 in result
        assert group2 in result
    
    def test_to_json(self):
        """Test converting schema to JSON."""
        group = CalendarGroup(name="test", calendar_ids=["cal1"])
        schema = GroupsSchema(version="1.0", groups={"test": group})
        
        json_str = schema.to_json()
        data = json.loads(json_str)
        
        assert data["version"] == "1.0"
        assert "test" in data["groups"]
        assert data["groups"]["test"]["name"] == "test"
        assert data["groups"]["test"]["calendar_ids"] == ["cal1"]
    
    def test_from_json(self):
        """Test creating schema from JSON."""
        json_data = {
            "version": "1.0",
            "groups": {
                "test": {
                    "name": "test",
                    "calendar_ids": ["cal1", "cal2"],
                    "description": "Test group",
                    "created": "2023-01-01T12:00:00",
                    "modified": "2023-01-02T12:00:00"
                }
            }
        }
        
        json_str = json.dumps(json_data)
        schema = GroupsSchema.from_json(json_str)
        
        assert schema.version == "1.0"
        assert "test" in schema.groups
        assert isinstance(schema.groups["test"], CalendarGroup)
        assert schema.groups["test"].name == "test"
        assert schema.groups["test"].calendar_ids == ["cal1", "cal2"]
    
    def test_to_dict(self):
        """Test converting schema to dictionary."""
        group = CalendarGroup(name="test", calendar_ids=["cal1"])
        schema = GroupsSchema(version="1.0", groups={"test": group})
        
        result = schema.to_dict()
        
        assert result["version"] == "1.0"
        assert "test" in result["groups"]
        assert isinstance(result["groups"]["test"], dict)
        assert result["groups"]["test"]["name"] == "test"
    
    def test_json_serialization_round_trip(self):
        """Test JSON serialization round trip."""
        original_group = CalendarGroup(
            name="test",
            calendar_ids=["cal1", "cal2"],
            description="Test group"
        )
        original_schema = GroupsSchema(
            version="1.0",
            groups={"test": original_group}
        )
        
        # Convert to JSON and back
        json_str = original_schema.to_json()
        restored_schema = GroupsSchema.from_json(json_str)
        
        assert restored_schema.version == original_schema.version
        assert len(restored_schema.groups) == 1
        assert "test" in restored_schema.groups
        
        restored_group = restored_schema.groups["test"]
        assert restored_group.name == original_group.name
        assert restored_group.calendar_ids == original_group.calendar_ids
        assert restored_group.description == original_group.description