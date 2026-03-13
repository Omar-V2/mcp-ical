# Comprehensive Timezone Handling Fix Plan

## Problem Summary

Based on issues #5 and #17 from upstream, and our own testing, there are multiple timezone-related problems:

1. **Model Layer Issue**: `convert_datetime()` creates naive datetime objects (no timezone)
2. **Display Issue**: Event strings don't show timezone information
3. **EventKit Incompatibility**: EventKit expects naive datetimes in local time, but we need to track timezone info
4. **Cross-timezone Matching**: When Claude provides datetimes in different timezones, occurrence matching fails
5. **Ambiguous Inputs**: Claude might send naive datetimes (which could be local time OR UTC)

## Core Principles

1. **Internal Representation**: All datetimes should be timezone-aware throughout our code
2. **EventKit Boundary**: Convert to naive local time only when calling EventKit APIs
3. **Be Kind to Claude**: Accept both naive (assume local time, fallback to UTC) and timezone-aware inputs
4. **Never Guess Wrong**: Better to fail explicitly than silently match the wrong occurrence

## Layer-by-Layer Approach

### Layer 1: Event Model (models.py)
**Goal**: Ensure all Event objects contain timezone-aware datetimes

**Changes needed**:
- `convert_datetime()`: Convert NSDate to timezone-aware datetime in local timezone
  ```python
  # Before: datetime.fromtimestamp(timestamp)  # naive
  # After:  datetime.fromtimestamp(timestamp, tz=timezone.utc).astimezone()  # aware in local tz
  ```
- Apply to: `start_time`, `end_time`, `last_modified`, `recurrence_rule.end_date`
- Update `__str__` to include timezone abbreviations for clarity

### Layer 2: CalendarManager Input Handling (ical.py)
**Goal**: Accept both naive and timezone-aware inputs from Claude, handle gracefully

**Changes needed**:
- `list_events()`: Accept timezone-aware `start_time`/`end_time`, convert to naive local for EventKit
- `create_event()`: Accept timezone-aware datetimes in request, convert to naive local for EventKit
- `update_event()`: Same as create_event
- Helper function: `to_eventkit_datetime(dt)` - converts aware→naive local, passes through naive

### Layer 3: Occurrence Matching (ical.py)
**Goal**: Match occurrences correctly even when Claude uses different timezone representations

**Changes needed**:
- `find_event_occurrence()`: Try matching in multiple ways:
  1. If timezone-aware: convert to local time for matching
  2. If naive: try as-is first, then try UTC interpretation
- `_search_occurrence_by_datetime()`: Convert all datetimes to naive local before EventKit predicate
- Use exact datetime equality after timezone normalization

### Layer 4: MCP Server Documentation (server.py)
**Goal**: Guide Claude on how to provide datetimes

**Updates needed**:
- Clarify that timezone-aware datetimes are preferred
- Document that naive datetimes are assumed to be local time (with UTC fallback)
- Update examples to show both formats work
- Remove conflicting guidance about timezone suffixes

### Layer 5: Testing
**Scenarios to cover**:
- Create event with timezone-aware datetime ✓
- Create event with naive datetime (local) ✓
- Update single occurrence with timezone-aware datetime ✓
- Update single occurrence with naive datetime ✓
- Cross-timezone matching (PST event, query from AEDT) ✓
- List events across timezone boundaries ✓
- Display events with timezone information ✓

## Implementation Order

1. **Commit 1**: Fix `convert_datetime()` in models.py (foundational)
2. **Commit 2**: Add `to_eventkit_datetime()` helper and use in CalendarManager
3. **Commit 3**: Fix occurrence matching with timezone normalization
4. **Commit 4**: Update MCP documentation to reflect new behavior
5. **Commit 5**: Add/update tests for all scenarios

## Key Decisions

- **Timezone-aware everywhere internally**: More explicit, prevents bugs
- **EventKit boundary conversion**: Only convert to naive at the last moment
- **Graceful fallback**: Try local interpretation first, then UTC for naive datetimes
- **Never fail silently**: If we can't find an occurrence, raise clear error
