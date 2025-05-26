# Release Notes

## Version 0.2.0 - Calendar Groups & Enhanced Management

*Released: January 22, 2025*

### 🎉 Major New Features

#### 📁 Calendar Groups
Transform how you organize and manage calendars across multiple accounts! Calendar Groups allow you to create logical collections of calendars from different sources (iCloud, Google, Office365, Exchange, etc.) for streamlined scheduling and event management.

**Key Features:**
- **Cross-Account Support**: Group calendars from any source together
- **Persistent Storage**: Groups persist between app launches with local JSON storage
- **Natural Language Integration**: Use groups in everyday calendar queries
- **Complete CRUD Operations**: Full create, read, update, delete support for groups

**Example Usage:**
```
"Create a Work group with my Office365 and Google work calendars"
"What meetings do I have in my Work calendars this week?"
"Add my Project calendar to the Work group"
"Show me all Family events for next month"
```

#### 📊 Enhanced Calendar Management
- **Account-Organized Listing**: View calendars grouped by account (iCloud, Google, etc.)
- **Default Calendar Highlighting**: Easily identify your default calendar
- **Multi-Source Integration**: Improved support for calendars from different providers

### 🛠️ New MCP Tools

The following new tools have been added to support calendar groups:

- `create_calendar_group(name, calendar_names, description)` - Create new custom groups
- `update_calendar_group(group_name, calendar_names, description)` - Modify group membership
- `delete_calendar_group(group_name)` - Remove custom groups
- `list_calendar_groups()` - List all custom groups
- `list_calendars_in_group(group_name)` - Get calendars within a specific group
- `list_events_by_group(start_date, end_date, group_name)` - Get events from all calendars in a group
- `add_calendar_to_group(group_name, calendar_name)` - Add individual calendars to groups
- `remove_calendar_from_group(group_name, calendar_name)` - Remove calendars from groups

### 🔧 Technical Improvements

- **Modular Architecture**: Calendar groups implemented with clean, testable package structure
- **Robust Storage Layer**: Atomic file operations with corruption recovery
- **Enhanced Error Handling**: Better validation and graceful handling of missing calendars
- **Performance Optimizations**: Efficient group-based event filtering
- **NSTaggedDate Compatibility**: Resolved compatibility issues for improved reliability

### 🏗️ Implementation Highlights

Calendar Groups are built on a solid foundation:

- **Storage Layer**: JSON-based persistence with atomic writes and backup support
- **Data Models**: Pydantic-based validation with schema versioning
- **Group Manager**: Business logic for CRUD operations with validation
- **Calendar Integration**: Bridge between groups and existing calendar system
- **MCP Tools**: Natural language interface for all group operations

### 📦 Dependencies

No new external dependencies added - calendar groups use only existing libraries (Pydantic, standard library JSON operations).

### 🔄 Backward Compatibility

All existing functionality remains unchanged. Calendar groups are an additive feature that doesn't affect existing workflows.

### 🧪 Testing

Comprehensive test coverage added:
- Unit tests for each component (storage, models, manager, integration, tools)
- Integration tests with real calendar data
- Edge case handling (missing calendars, corrupted files, validation errors)
- MCP protocol testing with FastMCP framework

---

## Version 0.1.0 - Initial Release

*Previous release*

### Features
- Natural language calendar event creation
- Smart schedule management and availability checking
- Intelligent event updates and modifications
- Multi-calendar support (iCloud, Google, Office365)
- macOS Calendar app integration
- MCP protocol compatibility