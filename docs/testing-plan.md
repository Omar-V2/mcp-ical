# MCP iCal Server Integration Testing Plan

## Overview

This document outlines a comprehensive testing strategy for validating the MCP iCal server integration with real calendar systems. The testing approach is divided into manual testing using Claude Desktop and automated testing using programmatic MCP client interactions.

## Testing Strategy

### Test Categories

1. **Unit Tests** ✅ (Already implemented)
   - Individual component validation
   - 118 tests covering storage, models, managers, and tools
   - Fast feedback during development

2. **Manual Integration Tests** 📋 (This document)
   - End-to-end user workflows via Claude Desktop
   - Real calendar system interaction
   - User experience validation

3. **Automated Integration Tests** 🤖 (Future implementation)
   - Programmatic MCP client testing
   - CI/CD pipeline integration
   - Regression testing

## Manual Testing with Claude Desktop

### Prerequisites

- macOS system with Calendar app configured
- Claude for Desktop installed
- MCP server configured as per [docs/install.md](install.md)
- Calendar permissions granted (Method 1 or Method 2)
- Test calendars created for safe testing

### Setup Instructions

1. **Prepare Test Environment**
   ```bash
   # 1. Clone and setup
   git clone https://github.com/Omar-V2/mcp-ical.git
   cd mcp-ical
   uv sync
   
   # 2. Configure Claude Desktop
   # Edit ~/Library/Application Support/Claude/claude_desktop_config.json
   ```

2. **Configure Test Calendars**
   - Create dedicated test calendars: "Test Personal", "Test Work", "Test Projects"
   - Ensure existing calendars have some sample events
   - Document calendar names for consistent testing

3. **Launch Claude with Calendar Access**
   ```bash
   /Applications/Claude.app/Contents/MacOS/Claude
   ```

### Manual Test Suite

#### Phase 1: Basic Calendar Operations

| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| TC-001 | "List all my calendars" | Returns list of available calendars |
| TC-002 | "What's my schedule for today?" | Shows today's events across calendars |
| TC-003 | "Create a test event tomorrow at 2 PM" | Creates event successfully |
| TC-004 | "Find the test event I just created" | Locates and displays the event |
| TC-005 | "Update the test event to 3 PM instead" | Modifies event time successfully |
| TC-006 | "Delete the test event" | Removes event from calendar |

#### Phase 2: Calendar Groups Core Functionality

| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| TC-101 | "Create a calendar group called 'Work' with Test Work and Test Projects calendars" | Creates group successfully |
| TC-102 | "List all my calendar groups" | Shows created groups with details |
| TC-103 | "Show me details of the Work group" | Displays group info and member calendars |
| TC-104 | "Add Test Personal calendar to the Work group" | Successfully adds calendar to group |
| TC-105 | "Remove Test Personal from the Work group" | Successfully removes calendar from group |
| TC-106 | "Rename the Work group to 'Professional'" | Updates group name successfully |
| TC-107 | "Delete the Professional group" | Removes group completely |

#### Phase 3: Advanced Group Operations

| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| TC-201 | "Create a 'Personal' group with just Test Personal calendar" | Creates single-calendar group |
| TC-202 | "Show me all events from my Personal group for next week" | Displays filtered events |
| TC-203 | "Which groups contain the Test Work calendar?" | Shows groups containing specified calendar |
| TC-204 | "What calendars are available that aren't in any group?" | Lists ungrouped calendars |
| TC-205 | "Create event in my Personal group for Friday at 5 PM" | Creates event in group's calendars |
| TC-206 | "Show me statistics for my Personal group" | Displays group usage statistics |

#### Phase 4: Error Handling and Edge Cases

| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| TC-301 | "Create a group called 'Personal'" (duplicate name) | Returns appropriate error message |
| TC-302 | "Add NonExistentCalendar to Personal group" | Handles invalid calendar gracefully |
| TC-303 | "Show events from NonExistentGroup" | Returns appropriate error message |
| TC-304 | "Delete NonExistentGroup" | Handles missing group gracefully |
| TC-305 | "Create group with empty name" | Validates input and shows error |
| TC-306 | "Add same calendar twice to a group" | Handles duplicates appropriately |

#### Phase 5: Complex Workflows

| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| TC-401 | Multi-step group creation and management | Complete workflow success |
| TC-402 | Event creation across multiple groups | Proper event distribution |
| TC-403 | Group reorganization (move calendars between groups) | Successful reorganization |
| TC-404 | Bulk operations (create multiple groups) | Efficient bulk processing |
| TC-405 | Recovery testing (restart Claude, verify persistence) | Data persistence validation |

### Manual Testing Checklist

#### Pre-Test Setup
- [ ] Test calendars created and populated
- [ ] Claude Desktop configured correctly
- [ ] Calendar permissions granted
- [ ] MCP server responds to basic commands

#### During Testing
- [ ] Document all commands used
- [ ] Note response times and user experience
- [ ] Capture screenshots of key interactions
- [ ] Record any unexpected behaviors
- [ ] Test both success and failure scenarios

#### Post-Test Validation
- [ ] Verify calendar data integrity
- [ ] Check group persistence across restarts
- [ ] Validate no data corruption occurred
- [ ] Clean up test data created during testing

## Automated Testing Strategy

### Automated Testing Overview

For automated testing, we need to programmatically interact with the MCP server using an MCP client library or Claude Code CLI.

### Option 1: Claude Code CLI Testing

```bash
# Example automated test script structure
#!/bin/bash

# Set environment variables for Claude Code
export CLAUDE_API_KEY="your-api-key"
export MCP_SERVER_CONFIG="path/to/mcp-ical-config.json"

# Test basic calendar operations
echo "Testing calendar listing..."
claude code "List all my calendars" --mcp-server mcp-ical

# Test group operations
echo "Testing group creation..."
claude code "Create a calendar group called 'TestGroup' with my work calendars" --mcp-server mcp-ical

# Validate responses
echo "Validating group was created..."
claude code "List all my calendar groups" --mcp-server mcp-ical | grep "TestGroup"
```

### Option 2: Direct MCP Protocol Testing

```python
# Example Python test using MCP client library
import asyncio
from mcp_client import MCPClient

async def test_calendar_groups():
    client = MCPClient()
    
    # Connect to MCP server
    await client.connect("stdio", command=["uv", "run", "mcp-ical"])
    
    # Test group creation
    result = await client.call_tool("create_calendar_group", {
        "name": "TestGroup",
        "calendar_names": ["Test Personal", "Test Work"],
        "description": "Automated test group"
    })
    
    assert "successfully" in result.lower()
    
    # Test group listing
    groups = await client.call_tool("list_calendar_groups", {})
    assert "TestGroup" in groups
    
    # Cleanup
    await client.call_tool("delete_calendar_group", {"name": "TestGroup"})
    await client.disconnect()

# Run automated tests
asyncio.run(test_calendar_groups())
```

### Continuous Integration Setup

```yaml
# .github/workflows/integration-tests.yml
name: MCP Integration Tests

on: [push, pull_request]

jobs:
  integration-test:
    runs-on: macos-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Setup Python and UV
      uses: actions/setup-python@v4
      with:
        python-version: '3.12'
    
    - name: Install dependencies
      run: |
        curl -LsSf https://astral.sh/uv/install.sh | sh
        uv sync
    
    - name: Setup test calendars
      run: |
        # Create test calendars using AppleScript or EventKit
        osascript -e 'tell application "Calendar" to make new calendar with properties {name:"Test Integration"}'
    
    - name: Run integration tests
      env:
        CLAUDE_API_KEY: ${{ secrets.CLAUDE_API_KEY }}
      run: |
        python tests/integration/test_mcp_integration.py
    
    - name: Cleanup test data
      run: |
        # Remove test calendars and groups
        python tests/integration/cleanup.py
```

### Automated Test Implementation Plan

#### Phase 1: Basic MCP Protocol Testing
- Test tool discovery and registration
- Validate tool schemas and parameters
- Test basic request/response flow

#### Phase 2: Calendar Groups Automation
- Automated group CRUD operations
- Batch testing with multiple scenarios
- Performance testing with large datasets

#### Phase 3: Regression Testing
- Test all manual scenarios programmatically
- Error injection and recovery testing
- Load testing with concurrent operations

#### Phase 4: CI/CD Integration
- Automated testing on every commit
- Performance benchmarking
- Security testing for calendar data

## Testing Data Management

### Test Data Setup

```bash
# Create test calendars
osascript -e '
tell application "Calendar"
    make new calendar with properties {name:"MCP Test Personal"}
    make new calendar with properties {name:"MCP Test Work"}
    make new calendar with properties {name:"MCP Test Projects"}
end tell
'

# Populate with test events
python scripts/create_test_events.py
```

### Test Data Cleanup

```bash
# Remove test calendars
osascript -e '
tell application "Calendar"
    delete calendar "MCP Test Personal"
    delete calendar "MCP Test Work"
    delete calendar "MCP Test Projects"
end tell
'

# Clean group storage
rm -f ~/Library/Application\ Support/mcp-ical/calendar_groups.json
```

## Performance Testing

### Metrics to Track

- **Response Time**: Tool execution time
- **Memory Usage**: Server memory consumption
- **Calendar Access**: EventKit operation efficiency
- **Storage I/O**: JSON file operations performance

### Performance Test Scenarios

1. **Large Group Operations**
   - Groups with 10+ calendars
   - Bulk event retrieval (1000+ events)
   - Concurrent group modifications

2. **Storage Performance**
   - Large groups.json file (100+ groups)
   - Frequent read/write operations
   - Atomic operation performance

3. **Calendar System Load**
   - Multiple calendar access operations
   - Large date range queries
   - Cross-calendar event searches

## Security Testing

### Security Considerations

1. **Calendar Data Privacy**
   - Verify no sensitive data leakage
   - Test permission boundaries
   - Validate data encryption at rest

2. **Input Validation**
   - Test malicious input handling
   - Validate parameter sanitization
   - Test SQL injection prevention (storage)

3. **Permission Testing**
   - Test behavior without calendar access
   - Validate graceful permission denials
   - Test permission revocation scenarios

## Reporting and Documentation

### Test Reports

Each test session should generate:

1. **Test Execution Report**
   - Pass/fail status for each test case
   - Performance metrics
   - Error logs and screenshots

2. **Bug Reports**
   - Issue description and reproduction steps
   - System environment details
   - Expected vs actual behavior

3. **User Experience Report**
   - Response quality assessment
   - Natural language processing accuracy
   - User workflow efficiency

### Success Criteria

#### Manual Testing Success
- [ ] All core functionality test cases pass
- [ ] Error handling works appropriately
- [ ] User experience meets quality standards
- [ ] No data corruption or loss
- [ ] Performance is acceptable (< 2s response time)

#### Automated Testing Success
- [ ] All automated test suites pass
- [ ] CI/CD pipeline integration successful
- [ ] Performance benchmarks met
- [ ] Security tests pass
- [ ] Regression tests prevent issues

## Conclusion

This testing plan provides comprehensive coverage for validating the MCP iCal server integration with real calendar systems. The combination of manual testing for user experience validation and automated testing for regression prevention ensures robust calendar groups functionality.

Regular execution of this testing plan will maintain high quality and reliability of the MCP server as it evolves and new features are added.