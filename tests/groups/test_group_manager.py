"""Unit tests for CalendarGroupManager class."""

import tempfile
from pathlib import Path
import pytest
from unittest.mock import Mock, patch

from mcp_ical.groups.group_manager import CalendarGroupManager
from mcp_ical.groups.storage import GroupStorage
from mcp_ical.groups.group_models import CalendarGroup


class TestCalendarGroupManager:
    """Test CalendarGroupManager functionality."""
    
    @pytest.fixture
    def temp_storage(self):
        """Create temporary storage for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir) / "test_groups.json"
            yield GroupStorage(str(storage_path))
    
    @pytest.fixture
    def manager(self, temp_storage):
        """Create CalendarGroupManager with temporary storage."""
        return CalendarGroupManager(temp_storage)
    
    @pytest.fixture
    def mock_storage(self):
        """Create mock storage for testing."""
        storage = Mock(spec=GroupStorage)
        storage.load_groups.return_value = {"version": "1.0", "groups": {}}
        return storage
    
    @pytest.fixture
    def manager_with_mock(self, mock_storage):
        """Create CalendarGroupManager with mock storage."""
        return CalendarGroupManager(mock_storage)
    
    def test_init_default_storage(self):
        """Test initialization with default storage."""
        manager = CalendarGroupManager()
        assert isinstance(manager.storage, GroupStorage)
    
    def test_init_custom_storage(self, temp_storage):
        """Test initialization with custom storage."""
        manager = CalendarGroupManager(temp_storage)
        assert manager.storage is temp_storage
    
    def test_create_group_basic(self, manager):
        """Test creating a basic group."""
        group = manager.create_group("work", ["cal1", "cal2"], "Work calendars")
        
        assert group.name == "work"
        assert group.calendar_ids == ["cal1", "cal2"]
        assert group.description == "Work calendars"
        
        # Verify it's persisted
        retrieved = manager.get_group("work")
        assert retrieved is not None
        assert retrieved.name == group.name
    
    def test_create_group_minimal(self, manager):
        """Test creating group with minimal parameters."""
        group = manager.create_group("minimal")
        
        assert group.name == "minimal"
        assert group.calendar_ids == []
        assert group.description == ""
    
    def test_create_group_duplicate_name(self, manager):
        """Test creating group with duplicate name fails."""
        manager.create_group("duplicate")
        
        with pytest.raises(ValueError) as exc_info:
            manager.create_group("duplicate")
        
        assert "already exists" in str(exc_info.value)
    
    def test_update_group_calendar_ids(self, manager):
        """Test updating group calendar IDs."""
        manager.create_group("test", ["cal1"])
        
        updated = manager.update_group("test", {"calendar_ids": ["cal1", "cal2", "cal3"]})
        
        assert updated.calendar_ids == ["cal1", "cal2", "cal3"]
        
        # Verify persistence
        retrieved = manager.get_group("test")
        assert retrieved.calendar_ids == ["cal1", "cal2", "cal3"]
    
    def test_update_group_description(self, manager):
        """Test updating group description."""
        manager.create_group("test", description="old description")
        
        updated = manager.update_group("test", {"description": "new description"})
        
        assert updated.description == "new description"
        
        # Verify persistence
        retrieved = manager.get_group("test")
        assert retrieved.description == "new description"
    
    def test_update_group_multiple_fields(self, manager):
        """Test updating multiple group fields."""
        manager.create_group("test", ["cal1"], "old")
        
        updated = manager.update_group("test", {
            "calendar_ids": ["cal2", "cal3"],
            "description": "new description"
        })
        
        assert updated.calendar_ids == ["cal2", "cal3"]
        assert updated.description == "new description"
    
    def test_update_group_nonexistent(self, manager):
        """Test updating non-existent group fails."""
        with pytest.raises(ValueError) as exc_info:
            manager.update_group("nonexistent", {"description": "test"})
        
        assert "not found" in str(exc_info.value)
    
    def test_delete_group_existing(self, manager):
        """Test deleting existing group."""
        manager.create_group("to_delete")
        
        result = manager.delete_group("to_delete")
        assert result is True
        
        # Verify it's gone
        assert manager.get_group("to_delete") is None
    
    def test_delete_group_nonexistent(self, manager):
        """Test deleting non-existent group."""
        result = manager.delete_group("nonexistent")
        assert result is False
    
    def test_get_group_existing(self, manager):
        """Test getting existing group."""
        created = manager.create_group("test", ["cal1"])
        retrieved = manager.get_group("test")
        
        assert retrieved is not None
        assert retrieved.name == created.name
        assert retrieved.calendar_ids == created.calendar_ids
    
    def test_get_group_nonexistent(self, manager):
        """Test getting non-existent group."""
        result = manager.get_group("nonexistent")
        assert result is None
    
    def test_list_groups_empty(self, manager):
        """Test listing groups when none exist."""
        groups = manager.list_groups()
        assert groups == []
    
    def test_list_groups_multiple(self, manager):
        """Test listing multiple groups."""
        manager.create_group("zebra")
        manager.create_group("alpha")
        manager.create_group("beta")
        
        groups = manager.list_groups()
        
        assert len(groups) == 3
        # Should be sorted by name
        names = [g.name for g in groups]
        assert names == ["alpha", "beta", "zebra"]
    
    def test_add_calendar_to_group(self, manager):
        """Test adding calendar to existing group."""
        manager.create_group("test", ["cal1"])
        
        result = manager.add_calendar_to_group("test", "cal2")
        assert result is True
        
        group = manager.get_group("test")
        assert "cal2" in group.calendar_ids
    
    def test_add_calendar_to_group_duplicate(self, manager):
        """Test adding duplicate calendar to group."""
        manager.create_group("test", ["cal1"])
        
        result = manager.add_calendar_to_group("test", "cal1")
        assert result is False
        
        # Calendar should still only appear once
        group = manager.get_group("test")
        assert group.calendar_ids.count("cal1") == 1
    
    def test_add_calendar_to_nonexistent_group(self, manager):
        """Test adding calendar to non-existent group."""
        with pytest.raises(ValueError) as exc_info:
            manager.add_calendar_to_group("nonexistent", "cal1")
        
        assert "not found" in str(exc_info.value)
    
    def test_remove_calendar_from_group(self, manager):
        """Test removing calendar from group."""
        manager.create_group("test", ["cal1", "cal2"])
        
        result = manager.remove_calendar_from_group("test", "cal1")
        assert result is True
        
        group = manager.get_group("test")
        assert "cal1" not in group.calendar_ids
        assert "cal2" in group.calendar_ids
    
    def test_remove_calendar_not_in_group(self, manager):
        """Test removing calendar not in group."""
        manager.create_group("test", ["cal1"])
        
        result = manager.remove_calendar_from_group("test", "cal2")
        assert result is False
        
        # Original calendar should still be there
        group = manager.get_group("test")
        assert group.calendar_ids == ["cal1"]
    
    def test_remove_calendar_from_nonexistent_group(self, manager):
        """Test removing calendar from non-existent group."""
        with pytest.raises(ValueError) as exc_info:
            manager.remove_calendar_from_group("nonexistent", "cal1")
        
        assert "not found" in str(exc_info.value)
    
    def test_get_calendars_in_group(self, manager):
        """Test getting calendars in group."""
        manager.create_group("test", ["cal1", "cal2", "cal3"])
        
        calendars = manager.get_calendars_in_group("test")
        assert calendars == ["cal1", "cal2", "cal3"]
        
        # Should return a copy, not the original list
        calendars.append("cal4")
        original = manager.get_group("test").calendar_ids
        assert "cal4" not in original
    
    def test_get_calendars_in_nonexistent_group(self, manager):
        """Test getting calendars from non-existent group."""
        with pytest.raises(ValueError) as exc_info:
            manager.get_calendars_in_group("nonexistent")
        
        assert "not found" in str(exc_info.value)
    
    def test_validate_calendar_exists(self, manager):
        """Test calendar validation."""
        # Placeholder implementation always returns True for non-empty strings
        assert manager.validate_calendar_exists("cal1") is True
        assert manager.validate_calendar_exists("") is False
        assert manager.validate_calendar_exists("   ") is False
    
    def test_get_groups_containing_calendar(self, manager):
        """Test finding groups containing a calendar."""
        manager.create_group("work", ["cal1", "cal2"])
        manager.create_group("personal", ["cal2", "cal3"])
        manager.create_group("empty", [])
        
        # Calendar in multiple groups
        groups = manager.get_groups_containing_calendar("cal2")
        names = [g.name for g in groups]
        assert set(names) == {"work", "personal"}
        
        # Calendar in one group
        groups = manager.get_groups_containing_calendar("cal1")
        assert len(groups) == 1
        assert groups[0].name == "work"
        
        # Calendar in no groups
        groups = manager.get_groups_containing_calendar("cal4")
        assert groups == []
    
    def test_rename_group(self, manager):
        """Test renaming a group."""
        manager.create_group("old_name", ["cal1"], "description")
        
        renamed = manager.rename_group("old_name", "new_name")
        
        assert renamed.name == "new_name"
        assert renamed.calendar_ids == ["cal1"]
        assert renamed.description == "description"
        
        # Old name should not exist
        assert manager.get_group("old_name") is None
        
        # New name should exist
        retrieved = manager.get_group("new_name")
        assert retrieved is not None
        assert retrieved.name == "new_name"
    
    def test_rename_group_nonexistent(self, manager):
        """Test renaming non-existent group."""
        with pytest.raises(ValueError) as exc_info:
            manager.rename_group("nonexistent", "new_name")
        
        assert "not found" in str(exc_info.value)
    
    def test_rename_group_name_conflict(self, manager):
        """Test renaming to existing name."""
        manager.create_group("group1")
        manager.create_group("group2")
        
        with pytest.raises(ValueError) as exc_info:
            manager.rename_group("group1", "group2")
        
        assert "already exists" in str(exc_info.value)
    
    def test_get_group_stats_empty(self, manager):
        """Test group statistics when no groups exist."""
        stats = manager.get_group_stats()
        
        expected = {
            "total_groups": 0,
            "total_calendars": 0,
            "average_calendars_per_group": 0,
            "largest_group": None,
            "smallest_group": None,
        }
        
        assert stats == expected
    
    def test_get_group_stats_with_groups(self, manager):
        """Test group statistics with multiple groups."""
        manager.create_group("small", ["cal1"])
        manager.create_group("large", ["cal1", "cal2", "cal3", "cal4"])
        manager.create_group("medium", ["cal2", "cal5"])
        
        stats = manager.get_group_stats()
        
        assert stats["total_groups"] == 3
        assert stats["total_calendars"] == 5  # cal1, cal2, cal3, cal4, cal5
        assert stats["average_calendars_per_group"] == (1 + 4 + 2) / 3
        
        assert stats["largest_group"]["name"] == "large"
        assert stats["largest_group"]["calendar_count"] == 4
        
        assert stats["smallest_group"]["name"] == "small"
        assert stats["smallest_group"]["calendar_count"] == 1
    
    def test_refresh_from_storage(self, manager_with_mock):
        """Test refreshing data from storage."""
        manager = manager_with_mock
        storage = manager.storage
        
        # Load initial data to populate cache
        manager.list_groups()
        
        # Verify cache is populated
        assert manager._schema_cache is not None
        
        # Refresh should invalidate cache
        manager.refresh_from_storage()
        assert manager._schema_cache is None
        
        # Next operation should reload from storage
        manager.list_groups()
        assert storage.load_groups.call_count >= 2
    
    def test_backup_groups(self, manager, temp_storage):
        """Test creating backup of groups."""
        # Create some groups first
        manager.create_group("test1", ["cal1"])
        manager.create_group("test2", ["cal2"])
        
        backup_path = manager.backup_groups()
        
        assert isinstance(backup_path, str)
        assert "calendar_groups_" in backup_path
        assert backup_path.endswith(".json")
        
        # Verify backup file exists
        from pathlib import Path
        assert Path(backup_path).exists()
    
    def test_schema_caching(self, manager_with_mock):
        """Test that schema is cached appropriately."""
        manager = manager_with_mock
        storage = manager.storage
        
        # First call should load from storage
        manager.list_groups()
        assert storage.load_groups.call_count == 1
        
        # Second call should use cache
        manager.list_groups()
        assert storage.load_groups.call_count == 1
        
        # Creating a group should save and maintain cache
        manager.create_group("test")
        assert storage.save_groups.call_count == 1
        
        # Subsequent reads should use cache
        manager.list_groups()
        assert storage.load_groups.call_count == 1
    
    def test_cache_invalidation_on_operations(self, manager_with_mock):
        """Test that cache is properly maintained on write operations."""
        manager = manager_with_mock
        storage = manager.storage
        
        # Load initial data
        initial_groups = manager.list_groups()
        assert len(initial_groups) == 0
        assert manager._schema_cache is not None
        
        # Write operations should maintain cache
        manager.create_group("test")
        assert manager._schema_cache is not None
        
        # Should be able to see the new group without reloading
        groups_after_create = manager.list_groups()
        assert len(groups_after_create) == 1
        assert groups_after_create[0].name == "test"
        
        # Delete should also maintain cache
        manager.delete_group("test")
        assert manager._schema_cache is not None
        
        # Should see empty list without reloading
        groups_after_delete = manager.list_groups()
        assert len(groups_after_delete) == 0