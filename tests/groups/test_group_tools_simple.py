"""Simplified unit tests for group tools business logic."""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch
import tempfile
from pathlib import Path

from mcp_ical.groups.group_tools import get_group_manager, get_group_bridge, register_group_tools
from mcp_ical.groups.storage import GroupStorage
from mcp_ical.groups.group_manager import CalendarGroupManager
from mcp_ical.groups.calendar_integration import GroupCalendarBridge
from mcp_ical.ical import CalendarManager
from mcp.server.fastmcp import FastMCP


class TestGroupToolsSimple:
    """Test group tools functionality without complex MCP integration."""
    
    @pytest.fixture
    def temp_storage(self):
        """Create temporary storage for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir) / "test_groups.json"
            yield GroupStorage(str(storage_path))
    
    @pytest.fixture
    def mock_calendar_manager(self):
        """Create mock CalendarManager."""
        mock = Mock(spec=CalendarManager)
        
        # Mock calendar objects
        mock_cal1 = Mock()
        mock_cal1.uniqueIdentifier.return_value = "cal-id-1"
        mock_cal1.title.return_value = "Work Calendar"
        
        mock_cal2 = Mock()
        mock_cal2.uniqueIdentifier.return_value = "cal-id-2"
        mock_cal2.title.return_value = "Personal Calendar"
        
        mock.list_calendars.return_value = [mock_cal1, mock_cal2]
        mock._find_calendar_by_name.side_effect = lambda name: {
            "Work Calendar": mock_cal1,
            "Personal Calendar": mock_cal2
        }.get(name)
        mock._find_calendar_by_id.side_effect = lambda cal_id: {
            "cal-id-1": mock_cal1,
            "cal-id-2": mock_cal2
        }.get(cal_id)
        
        return mock
    
    @pytest.fixture
    def group_manager(self, temp_storage):
        """Create CalendarGroupManager with temporary storage."""
        return CalendarGroupManager(temp_storage)
    
    @pytest.fixture
    def bridge(self, mock_calendar_manager, group_manager):
        """Create GroupCalendarBridge."""
        return GroupCalendarBridge(mock_calendar_manager, group_manager)
    
    @pytest.fixture
    def clear_caches(self):
        """Clear LRU caches before each test."""
        get_group_manager.cache_clear()
        get_group_bridge.cache_clear()
        yield
        get_group_manager.cache_clear()
        get_group_bridge.cache_clear()
    
    def test_get_group_manager_cache(self, clear_caches):
        """Test that group manager is cached."""
        manager1 = get_group_manager()
        manager2 = get_group_manager()
        
        # Should return the same instance due to caching
        assert manager1 is manager2
        assert isinstance(manager1, CalendarGroupManager)
    
    def test_get_group_bridge_cache(self, mock_calendar_manager, clear_caches):
        """Test that group bridge is cached."""
        bridge1 = get_group_bridge(mock_calendar_manager)
        bridge2 = get_group_bridge(mock_calendar_manager)
        
        # Should return the same instance due to caching
        assert bridge1 is bridge2
        assert isinstance(bridge1, GroupCalendarBridge)
    
    def test_register_group_tools_no_error(self, mock_calendar_manager):
        """Test that registering group tools doesn't throw errors."""
        app = FastMCP("Test")
        get_calendar_manager_func = lambda: mock_calendar_manager
        
        # This should complete without errors
        register_group_tools(app, get_calendar_manager_func)
        
        # Basic smoke test
        assert True
    
    def test_create_group_workflow(self, bridge):
        """Test the complete group creation workflow."""
        # Test the bridge method that would be called by the MCP tool
        result = bridge.create_group_from_calendar_names(
            "test_group",
            ["Work Calendar", "Personal Calendar"],
            "Test description"
        )
        
        assert "Successfully created group 'test_group' with 2 calendars" in result
        
        # Verify the group was created
        group = bridge.group_manager.get_group("test_group")
        assert group is not None
        assert group.name == "test_group"
        assert group.description == "Test description"
        assert len(group.calendar_ids) == 2
    
    def test_list_groups_workflow(self, bridge):
        """Test listing groups workflow."""
        # Create some test groups
        bridge.create_group_from_calendar_names("group1", ["Work Calendar"])
        bridge.create_group_from_calendar_names("group2", ["Personal Calendar"], "Personal stuff")
        
        # Get groups like the MCP tool would
        groups = bridge.group_manager.list_groups()
        
        assert len(groups) == 2
        group_names = {g.name for g in groups}
        assert group_names == {"group1", "group2"}
    
    def test_get_events_workflow(self, bridge, mock_calendar_manager):
        """Test getting events by group workflow."""
        # Mock events
        mock_event = Mock()
        mock_event.start_time = datetime(2023, 12, 1, 9, 0)
        mock_event.title = "Test Event"
        mock_event.calendar_name = "Work Calendar"
        mock_event.all_day = False
        mock_event.location = None
        
        mock_calendar_manager.list_events.return_value = [mock_event]
        
        # Create group first
        bridge.create_group_from_calendar_names("test_events", ["Work Calendar"])
        
        # Get events like the MCP tool would
        events = bridge.get_events_by_group(
            "test_events",
            datetime(2023, 12, 1),
            datetime(2023, 12, 1, 23, 59, 59)
        )
        
        assert len(events) == 1
        assert events[0].title == "Test Event"
    
    def test_group_validation_workflow(self, bridge):
        """Test group validation workflow."""
        # Create group
        bridge.create_group_from_calendar_names("validation_test", ["Work Calendar", "Personal Calendar"])
        
        # Validate like the MCP tool would
        validation_results = bridge.validate_group_calendars("validation_test")
        
        # All calendars should be valid in our mock setup
        assert all(validation_results.values())
        assert len(validation_results) == 2
    
    def test_add_remove_calendar_workflow(self, bridge):
        """Test adding and removing calendars from groups."""
        # Create group with one calendar
        bridge.create_group_from_calendar_names("modify_test", ["Work Calendar"])
        
        # Add calendar like MCP tool would
        result = bridge.add_calendar_to_group_by_name("modify_test", "Personal Calendar")
        assert result is True
        
        # Verify it was added
        group = bridge.group_manager.get_group("modify_test")
        assert len(group.calendar_ids) == 2
        
        # Remove calendar like MCP tool would
        result = bridge.remove_calendar_from_group_by_name("modify_test", "Personal Calendar")
        assert result is True
        
        # Verify it was removed
        group = bridge.group_manager.get_group("modify_test")
        assert len(group.calendar_ids) == 1
    
    def test_error_handling_workflow(self, bridge):
        """Test error handling in workflows."""
        # Test with non-existent calendar
        with pytest.raises(ValueError) as exc_info:
            bridge.create_group_from_calendar_names("error_test", ["Nonexistent Calendar"])
        
        assert "not found" in str(exc_info.value)
        
        # Test with non-existent group
        with pytest.raises(ValueError) as exc_info:
            bridge.get_events_by_group("nonexistent", datetime.now(), datetime.now())
        
        assert "not found" in str(exc_info.value)
    
    def test_groups_statistics_workflow(self, bridge):
        """Test getting group statistics."""
        # Create some groups
        bridge.create_group_from_calendar_names("stats1", ["Work Calendar"])
        bridge.create_group_from_calendar_names("stats2", ["Personal Calendar"])
        
        # Get stats like MCP tool would
        stats = bridge.get_group_statistics()
        
        assert stats["total_groups"] == 2
        assert stats["total_available_calendars"] == 2
        assert stats["calendars_in_groups"] == 2
        assert stats["ungrouped_calendars"] == 0
        assert stats["group_coverage_percentage"] == 100.0
    
    def test_cleanup_workflow(self, bridge):
        """Test cleanup invalid calendars workflow."""
        # Create group with valid calendars
        bridge.create_group_from_calendar_names("cleanup_test", ["Work Calendar"])
        
        # Cleanup should find no invalid calendars
        result = bridge.cleanup_invalid_calendars("cleanup_test")
        
        assert result["removed_count"] == 0
        assert result["group_name"] == "cleanup_test"
    
    def test_find_groups_for_calendar_workflow(self, bridge):
        """Test finding groups containing a calendar."""
        # Create groups with same calendar
        bridge.create_group_from_calendar_names("find1", ["Work Calendar"])
        bridge.create_group_from_calendar_names("find2", ["Work Calendar", "Personal Calendar"])
        
        # Find groups like MCP tool would
        groups = bridge.get_groups_for_calendar_name("Work Calendar")
        
        assert len(groups) == 2
        assert set(groups) == {"find1", "find2"}
    
    def test_get_calendar_info_workflow(self, bridge):
        """Test getting calendar info for group."""
        # Create group
        bridge.create_group_from_calendar_names("info_test", ["Work Calendar", "Personal Calendar"])
        
        # Get calendar info like MCP tool would
        info = bridge.get_calendar_info_for_group("info_test")
        
        assert len(info) == 2
        assert all(cal_info["exists"] for cal_info in info)
        calendar_names = {cal_info["name"] for cal_info in info}
        assert calendar_names == {"Work Calendar", "Personal Calendar"}