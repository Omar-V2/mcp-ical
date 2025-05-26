# Calendar Groups Architecture

## Overview
Calendar Groups provide cross-account calendar organization with persistent local storage. The implementation uses a clean separation of concerns across 5 main components.

## Code Structure

### `group_models.py` - Data Models
**Purpose:** Pydantic models for data validation and serialization

**Key Classes:**
- `CalendarGroup` - Individual group with name, calendar IDs, description, timestamps
- `GroupsSchema` - Complete storage file structure with versioning

**Responsibilities:**
- Field validation and constraints
- JSON serialization/deserialization
- Schema versioning for migrations

---

### `storage.py` - Persistence Layer
**Purpose:** Atomic JSON file operations with error recovery

**Key Features:**
- Atomic writes (temp file + rename pattern)
- Automatic backups before modifications
- Schema migration support
- Corruption recovery from backups

**Storage Location:** `~/Library/Application Support/mcp-ical/calendar_groups.json`

---

### `group_manager.py` - Business Logic
**Purpose:** Core CRUD operations and group management

**Key Operations:**
- Group creation, updating, deletion
- Calendar addition/removal from groups
- Group validation and statistics
- Schema caching for performance

**Notable:** Handles all business rules and data consistency

---

### `calendar_integration.py` - Calendar Bridge
**Purpose:** Connect groups with existing calendar system

**Key Functions:**
- Event retrieval across multiple calendars in a group
- Calendar name ↔ ID resolution and validation
- Group validation against actual calendar availability
- Cleanup utilities for invalid calendar references

**Integration:** Works with existing `CalendarManager` from `ical.py`

---

### `group_tools.py` - MCP API Layer
**Purpose:** External interface via MCP protocol

**Provides 12 MCP Tools:**
- Group CRUD operations
- Calendar membership management
- Group-based event queries
- User-friendly calendar name interfaces

**Notable:** Translates between user-friendly names and internal calendar IDs

## Data Flow

```
User Query → MCP Tools → Calendar Integration → Group Manager → Storage
                    ↓
               Calendar System (EventKit)
```

## Key Design Decisions

### Why This Architecture?
- **Separation of Concerns:** Each component has a single responsibility
- **Testability:** Each layer can be tested independently
- **Maintainability:** Changes to one layer don't affect others
- **Performance:** Caching at manager level, atomic operations at storage level

### Storage Strategy
- **Local JSON:** No cloud dependencies, fast access
- **Calendar IDs:** Persistent across name changes
- **Atomic Operations:** Prevents corruption during writes
- **Schema Versioning:** Enables future migrations

### Error Handling
- **Graceful Degradation:** Invalid calendars are flagged but don't break groups
- **Recovery Mechanisms:** Automatic backup restoration
- **User Feedback:** Clear error messages through MCP tools

## Extension Points

### Adding New Features
- **New MCP Tools:** Add to `group_tools.py`
- **New Group Properties:** Extend `CalendarGroup` model
- **New Storage Formats:** Implement in `storage.py` with migration
- **New Calendar Sources:** Extend `calendar_integration.py`

### Performance Considerations
- Schema caching in `group_manager.py`
- Lazy loading of calendar validation
- Efficient JSON serialization
- Minimal EventKit calls through existing `CalendarManager`