"""Unit tests for GroupCalendarBridge class."""

from datetime import datetime
from unittest.mock import Mock, MagicMock
import pytest

from mcp_ical.groups.calendar_integration import GroupCalendarBridge
from mcp_ical.groups.group_manager import CalendarGroupManager
from mcp_ical.groups.group_models import CalendarGroup
from mcp_ical.ical import CalendarManager, NoSuchCalendarException
from mcp_ical.models import Event


class TestGroupCalendarBridge:
    """Test GroupCalendarBridge functionality."""
    
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
        
        mock_cal3 = Mock()
        mock_cal3.uniqueIdentifier.return_value = "cal-id-3"
        mock_cal3.title.return_value = "Project Calendar"
        
        # Setup method returns
        mock.list_calendars.return_value = [mock_cal1, mock_cal2, mock_cal3]
        mock.list_calendar_names.return_value = ["Work Calendar", "Personal Calendar", "Project Calendar"]
        
        # Setup find methods
        def find_by_name(name):
            name_map = {
                "Work Calendar": mock_cal1,
                "Personal Calendar": mock_cal2,
                "Project Calendar": mock_cal3
            }
            return name_map.get(name)
        
        def find_by_id(cal_id):
            id_map = {
                "cal-id-1": mock_cal1,
                "cal-id-2": mock_cal2,
                "cal-id-3": mock_cal3
            }
            return id_map.get(cal_id)
        
        mock._find_calendar_by_name = find_by_name
        mock._find_calendar_by_id = find_by_id
        
        return mock
    
    @pytest.fixture
    def mock_group_manager(self):
        """Create mock CalendarGroupManager."""
        mock = Mock(spec=CalendarGroupManager)
        
        # Create some test groups
        work_group = CalendarGroup(
            name="work",
            calendar_ids=["cal-id-1", "cal-id-3"],
            description="Work related calendars"
        )
        
        personal_group = CalendarGroup(
            name="personal",
            calendar_ids=["cal-id-2"],
            description="Personal calendar"
        )
        
        # Setup method returns
        mock.get_group.side_effect = lambda name: {
            "work": work_group,
            "personal": personal_group
        }.get(name)
        
        mock.list_groups.return_value = [work_group, personal_group]
        mock.get_groups_containing_calendar.return_value = []
        
        return mock
    
    @pytest.fixture
    def bridge(self, mock_calendar_manager, mock_group_manager):
        """Create GroupCalendarBridge with mocks."""
        return GroupCalendarBridge(mock_calendar_manager, mock_group_manager)
    
    def test_init_with_managers(self, mock_calendar_manager, mock_group_manager):
        """Test initialization with provided managers."""
        bridge = GroupCalendarBridge(mock_calendar_manager, mock_group_manager)
        
        assert bridge.calendar_manager is mock_calendar_manager
        assert bridge.group_manager is mock_group_manager
    
    def test_init_with_default_group_manager(self, mock_calendar_manager):
        """Test initialization with default group manager."""
        bridge = GroupCalendarBridge(mock_calendar_manager)
        
        assert bridge.calendar_manager is mock_calendar_manager
        assert isinstance(bridge.group_manager, CalendarGroupManager)
    
    def test_get_events_by_group_success(self, bridge, mock_calendar_manager):
        """Test getting events by group successfully."""
        # Setup mock events
        mock_event1 = Mock(spec=Event)
        mock_event1.start_time = datetime(2023, 1, 1, 10, 0)
        mock_event2 = Mock(spec=Event)
        mock_event2.start_time = datetime(2023, 1, 1, 14, 0)
        
        mock_calendar_manager.list_events.side_effect = [
            [mock_event1],  # Work Calendar events
            [mock_event2]   # Project Calendar events
        ]
        
        start_date = datetime(2023, 1, 1)
        end_date = datetime(2023, 1, 31)
        
        events = bridge.get_events_by_group("work", start_date, end_date)
        
        assert len(events) == 2
        assert events[0] is mock_event1  # Should be sorted by start_time
        assert events[1] is mock_event2
        
        # Verify calendar manager was called correctly
        assert mock_calendar_manager.list_events.call_count == 2
        mock_calendar_manager.list_events.assert_any_call(start_date, end_date, "Work Calendar")
        mock_calendar_manager.list_events.assert_any_call(start_date, end_date, "Project Calendar")
    
    def test_get_events_by_group_nonexistent_group(self, bridge):
        """Test getting events for non-existent group."""
        start_date = datetime(2023, 1, 1)
        end_date = datetime(2023, 1, 31)
        
        with pytest.raises(ValueError) as exc_info:
            bridge.get_events_by_group("nonexistent", start_date, end_date)
        
        assert "not found" in str(exc_info.value)
    
    def test_get_events_by_group_with_missing_calendar(self, bridge, mock_calendar_manager):
        """Test getting events when some calendars no longer exist."""
        # Make one calendar lookup fail
        def side_effect(start_date, end_date, calendar_name):
            if calendar_name == "Work Calendar":
                return [Mock()]
            else:
                raise NoSuchCalendarException(calendar_name)
        
        mock_calendar_manager.list_events.side_effect = side_effect
        
        start_date = datetime(2023, 1, 1)
        end_date = datetime(2023, 1, 31)
        
        # Should not raise exception, just skip missing calendars
        events = bridge.get_events_by_group("work", start_date, end_date)
        
        assert len(events) == 1
    
    def test_validate_group_calendars(self, bridge):
        """Test validating calendars in a group."""
        result = bridge.validate_group_calendars("work")
        
        expected = {
            "cal-id-1": True,   # Work Calendar exists
            "cal-id-3": True    # Project Calendar exists
        }
        
        assert result == expected
    
    def test_validate_group_calendars_nonexistent_group(self, bridge):
        """Test validating non-existent group."""
        with pytest.raises(ValueError) as exc_info:
            bridge.validate_group_calendars("nonexistent")
        
        assert "not found" in str(exc_info.value)
    
    def test_validate_group_calendars_with_invalid_calendars(self, bridge, mock_group_manager):
        """Test validating group with some invalid calendars."""
        # Create group with invalid calendar ID
        invalid_group = CalendarGroup(
            name="invalid",
            calendar_ids=["cal-id-1", "invalid-id", "cal-id-2"],
            description="Group with invalid calendar"
        )
        
        # Override the get_group method for this specific test
        def get_group_side_effect(name):
            if name == "invalid":
                return invalid_group
            # Fall back to original mock behavior for other groups
            return {
                "work": CalendarGroup(name="work", calendar_ids=["cal-id-1", "cal-id-3"]),
                "personal": CalendarGroup(name="personal", calendar_ids=["cal-id-2"])
            }.get(name)
        
        mock_group_manager.get_group.side_effect = get_group_side_effect
        
        result = bridge.validate_group_calendars("invalid")
        
        expected = {
            "cal-id-1": True,
            "invalid-id": False,
            "cal-id-2": True
        }
        
        assert result == expected
    
    def test_resolve_calendar_names_to_ids(self, bridge):
        """Test resolving calendar names to IDs."""
        names = ["Work Calendar", "Personal Calendar"]
        ids = bridge.resolve_calendar_names_to_ids(names)
        
        assert ids == ["cal-id-1", "cal-id-2"]
    
    def test_resolve_calendar_names_to_ids_invalid_name(self, bridge):
        """Test resolving invalid calendar name."""
        names = ["Work Calendar", "Nonexistent Calendar"]
        
        with pytest.raises(ValueError) as exc_info:
            bridge.resolve_calendar_names_to_ids(names)
        
        assert "Nonexistent Calendar" in str(exc_info.value)
    
    def test_resolve_calendar_ids_to_names(self, bridge):
        """Test resolving calendar IDs to names."""
        ids = ["cal-id-1", "cal-id-2"]
        names = bridge.resolve_calendar_ids_to_names(ids)
        
        assert names == ["Work Calendar", "Personal Calendar"]
    
    def test_resolve_calendar_ids_to_names_invalid_id(self, bridge):
        """Test resolving invalid calendar ID."""
        ids = ["cal-id-1", "invalid-id"]
        
        with pytest.raises(ValueError) as exc_info:
            bridge.resolve_calendar_ids_to_names(ids)
        
        assert "invalid-id" in str(exc_info.value)
    
    def test_get_calendar_info_for_group(self, bridge):
        """Test getting calendar info for a group."""
        info = bridge.get_calendar_info_for_group("work")
        
        expected = [
            {
                "id": "cal-id-1",
                "name": "Work Calendar",
                "exists": True,
                "group": "work"
            },
            {
                "id": "cal-id-3", 
                "name": "Project Calendar",
                "exists": True,
                "group": "work"
            }
        ]
        
        assert info == expected
    
    def test_get_calendar_info_for_group_nonexistent(self, bridge):
        """Test getting calendar info for non-existent group."""
        with pytest.raises(ValueError) as exc_info:
            bridge.get_calendar_info_for_group("nonexistent")
        
        assert "not found" in str(exc_info.value)
    
    def test_get_groups_for_calendar(self, bridge, mock_group_manager):
        """Test getting groups that contain a calendar."""
        # Setup mock to return groups containing calendar
        mock_groups = [
            CalendarGroup(name="group1", calendar_ids=["cal-id-1"]),
            CalendarGroup(name="group2", calendar_ids=["cal-id-1"])
        ]
        mock_group_manager.get_groups_containing_calendar.return_value = mock_groups
        
        groups = bridge.get_groups_for_calendar("cal-id-1")
        
        assert groups == ["group1", "group2"]
        mock_group_manager.get_groups_containing_calendar.assert_called_once_with("cal-id-1")
    
    def test_get_groups_for_calendar_name(self, bridge, mock_group_manager):
        """Test getting groups for calendar by name."""
        mock_groups = [CalendarGroup(name="group1", calendar_ids=["cal-id-1"])]
        mock_group_manager.get_groups_containing_calendar.return_value = mock_groups
        
        groups = bridge.get_groups_for_calendar_name("Work Calendar")
        
        assert groups == ["group1"]
        mock_group_manager.get_groups_containing_calendar.assert_called_once_with("cal-id-1")
    
    def test_get_groups_for_calendar_name_invalid(self, bridge):
        """Test getting groups for invalid calendar name."""
        with pytest.raises(ValueError) as exc_info:
            bridge.get_groups_for_calendar_name("Nonexistent Calendar")
        
        assert "not found" in str(exc_info.value)
    
    def test_create_group_from_calendar_names(self, bridge, mock_group_manager):
        """Test creating group from calendar names."""
        calendar_names = ["Work Calendar", "Personal Calendar"]
        
        # Mock group creation
        mock_group = CalendarGroup(name="new_group", calendar_ids=["cal-id-1", "cal-id-2"])
        mock_group_manager.create_group.return_value = mock_group
        
        result = bridge.create_group_from_calendar_names("new_group", calendar_names, "Test group")
        
        assert "Successfully created group 'new_group' with 2 calendars" in result
        mock_group_manager.create_group.assert_called_once_with(
            "new_group", ["cal-id-1", "cal-id-2"], "Test group"
        )
    
    def test_add_calendar_to_group_by_name(self, bridge, mock_group_manager):
        """Test adding calendar to group by name."""
        mock_group_manager.add_calendar_to_group.return_value = True
        
        result = bridge.add_calendar_to_group_by_name("work", "Personal Calendar")
        
        assert result is True
        mock_group_manager.add_calendar_to_group.assert_called_once_with("work", "cal-id-2")
    
    def test_add_calendar_to_group_by_name_invalid_calendar(self, bridge):
        """Test adding invalid calendar to group by name."""
        with pytest.raises(ValueError) as exc_info:
            bridge.add_calendar_to_group_by_name("work", "Nonexistent Calendar")
        
        assert "not found" in str(exc_info.value)
    
    def test_remove_calendar_from_group_by_name(self, bridge, mock_group_manager):
        """Test removing calendar from group by name."""
        mock_group_manager.remove_calendar_from_group.return_value = True
        
        result = bridge.remove_calendar_from_group_by_name("work", "Work Calendar")
        
        assert result is True
        mock_group_manager.remove_calendar_from_group.assert_called_once_with("work", "cal-id-1")
    
    def test_cleanup_invalid_calendars(self, bridge, mock_group_manager):
        """Test cleaning up invalid calendars from group."""
        # Create group with invalid calendar
        invalid_group = CalendarGroup(
            name="cleanup_test",
            calendar_ids=["cal-id-1", "invalid-id", "cal-id-2"]
        )
        
        # Override the get_group method for this specific test
        def get_group_side_effect(name):
            if name == "cleanup_test":
                return invalid_group
            # Fall back to original mock behavior for other groups
            return {
                "work": CalendarGroup(name="work", calendar_ids=["cal-id-1", "cal-id-3"]),
                "personal": CalendarGroup(name="personal", calendar_ids=["cal-id-2"])
            }.get(name)
        
        mock_group_manager.get_group.side_effect = get_group_side_effect
        mock_group_manager.remove_calendar_from_group.return_value = True
        
        result = bridge.cleanup_invalid_calendars("cleanup_test")
        
        expected = {
            "group_name": "cleanup_test",
            "removed_count": 1,
            "invalid_calendars": ["invalid-id"],
            "remaining_calendars": 2
        }
        
        assert result == expected
        mock_group_manager.remove_calendar_from_group.assert_called_once_with("cleanup_test", "invalid-id")
    
    def test_get_available_calendars(self, bridge):
        """Test getting available calendars."""
        calendars = bridge.get_available_calendars()
        
        expected = {
            "cal-id-1": "Work Calendar",
            "cal-id-2": "Personal Calendar", 
            "cal-id-3": "Project Calendar"
        }
        
        assert calendars == expected
    
    def test_get_group_statistics(self, bridge, mock_group_manager):
        """Test getting comprehensive group statistics."""
        # Mock group stats
        mock_group_stats = {
            "total_groups": 2,
            "total_calendars": 2,
            "average_calendars_per_group": 1.5
        }
        mock_group_manager.get_group_stats.return_value = mock_group_stats
        
        # Set up list_groups to return the expected groups
        work_group = CalendarGroup(name="work", calendar_ids=["cal-id-1", "cal-id-3"])
        personal_group = CalendarGroup(name="personal", calendar_ids=["cal-id-2"])
        mock_group_manager.list_groups.return_value = [work_group, personal_group]
        
        stats = bridge.get_group_statistics()
        
        # Should include original stats plus integration stats
        assert stats["total_groups"] == 2
        assert stats["total_available_calendars"] == 3
        assert stats["calendars_in_groups"] == 3  # All calendars are in groups
        assert stats["ungrouped_calendars"] == 0  # No ungrouped calendars
        assert stats["invalid_calendar_references"] == 0
        assert stats["group_coverage_percentage"] == 100.0
    
    def test_internal_helper_methods(self, bridge):
        """Test internal helper methods."""
        # Test _get_calendar_id_by_name
        assert bridge._get_calendar_id_by_name("Work Calendar") == "cal-id-1"
        assert bridge._get_calendar_id_by_name("Nonexistent") is None
        
        # Test _get_calendar_name_by_id
        assert bridge._get_calendar_name_by_id("cal-id-1") == "Work Calendar"
        assert bridge._get_calendar_name_by_id("invalid-id") is None
        
        # Test _get_available_calendar_ids
        available_ids = bridge._get_available_calendar_ids()
        expected_ids = {"cal-id-1", "cal-id-2", "cal-id-3"}
        assert available_ids == expected_ids