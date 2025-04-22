import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.mcp_ical.ical import CalendarManager, NoSuchEventException
from src.mcp_ical.models import CreateEventRequest, Event
from src.mcp_ical.server import delete_event, get_calendar_manager


@pytest.fixture
def mock_calendar_manager():
    """Create a mock calendar manager for testing."""
    manager = MagicMock(spec=CalendarManager)
    return manager


@pytest.fixture
def mock_get_calendar_manager(mock_calendar_manager):
    """Mock the get_calendar_manager function to return our mock."""
    with patch("src.mcp_ical.server.get_calendar_manager", return_value=mock_calendar_manager):
        yield mock_calendar_manager


@pytest.mark.asyncio
async def test_delete_event_success(mock_get_calendar_manager):
    """Test successfully deleting an event."""
    # Setup
    event_id = "test-event-id"
    mock_event = MagicMock(spec=Event)
    mock_event.title = "Test Event"
    
    # Configure the mock calendar manager
    mock_get_calendar_manager.find_event_by_id.return_value = mock_event
    mock_get_calendar_manager.delete_event.return_value = True
    
    # Call the delete_event tool
    result = await delete_event(event_id)
    
    # Verify
    mock_get_calendar_manager.find_event_by_id.assert_called_once_with(event_id)
    mock_get_calendar_manager.delete_event.assert_called_once_with(event_id, True)
    assert "Successfully deleted event: Test Event" in result
    assert "and all future occurrences" in result


@pytest.mark.asyncio
async def test_delete_event_not_found(mock_get_calendar_manager):
    """Test deleting an event that doesn't exist."""
    # Setup
    event_id = "nonexistent-event-id"
    
    # Configure the mock calendar manager
    mock_get_calendar_manager.find_event_by_id.return_value = None
    
    # Call the delete_event tool
    result = await delete_event(event_id)
    
    # Verify
    mock_get_calendar_manager.find_event_by_id.assert_called_once_with(event_id)
    mock_get_calendar_manager.delete_event.assert_not_called()
    assert f"Event with ID {event_id} not found" in result


@pytest.mark.asyncio
async def test_delete_event_exception(mock_get_calendar_manager):
    """Test handling an exception during event deletion."""
    # Setup
    event_id = "test-event-id"
    mock_event = MagicMock(spec=Event)
    mock_event.title = "Test Event"
    
    # Configure the mock calendar manager
    mock_get_calendar_manager.find_event_by_id.return_value = mock_event
    mock_get_calendar_manager.delete_event.side_effect = Exception("Test error")
    
    # Call the delete_event tool
    result = await delete_event(event_id)
    
    # Verify
    mock_get_calendar_manager.find_event_by_id.assert_called_once_with(event_id)
    mock_get_calendar_manager.delete_event.assert_called_once_with(event_id, True)
    assert "Error deleting event: Test error" in result


@pytest.mark.asyncio
async def test_delete_event_deletion_failure(mock_get_calendar_manager):
    """Test when the delete_event method returns False."""
    # Setup
    event_id = "test-event-id"
    mock_event = MagicMock(spec=Event)
    mock_event.title = "Test Event"
    
    # Configure the mock calendar manager
    mock_get_calendar_manager.find_event_by_id.return_value = mock_event
    mock_get_calendar_manager.delete_event.return_value = False
    
    # Call the delete_event tool
    result = await delete_event(event_id)
    
    # Verify
    mock_get_calendar_manager.find_event_by_id.assert_called_once_with(event_id)
    mock_get_calendar_manager.delete_event.assert_called_once_with(event_id, True)
    assert f"Failed to delete event with ID {event_id}" in result


@pytest.mark.asyncio
async def test_delete_event_single_occurrence(mock_get_calendar_manager):
    """Test deleting only a single occurrence of a recurring event."""
    # Setup
    event_id = "recurring-event-id"
    mock_event = MagicMock(spec=Event)
    mock_event.title = "Recurring Event"
    
    # Configure the mock calendar manager
    mock_get_calendar_manager.find_event_by_id.return_value = mock_event
    mock_get_calendar_manager.delete_event.return_value = True
    
    # Call the delete_event tool with delete_entire_series=False
    result = await delete_event(event_id, delete_entire_series=False)
    
    # Verify
    mock_get_calendar_manager.find_event_by_id.assert_called_once_with(event_id)
    mock_get_calendar_manager.delete_event.assert_called_once_with(event_id, False)
    assert "Successfully deleted event: Recurring Event" in result
    assert "(this occurrence only)" in result