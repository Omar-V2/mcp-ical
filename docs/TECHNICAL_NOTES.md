# Calendar Groups Technical Notes

## Research Findings

### EventKit Limitations
**EKCalendarGroup does not exist** in Apple's EventKit framework. EventKit only supports account-based organization via `EKSource` objects, which cannot span multiple accounts. This is why calendar groups required implementing a custom persistence layer rather than using native EventKit grouping.

## Known Edge Cases

### Calendar System Behavior
- **Calendar Identifiers**: Can change in rare cases (usually during account re-authentication)
- **Calendar Names**: Not unique across accounts - multiple calendars can have the same display name
- **Account Synchronization**: Calendar availability can be delayed during account sync operations

### File System Considerations  
- **Concurrent Access**: Multiple MCP server instances could theoretically conflict on storage file
- **Permission Changes**: macOS security updates can affect Application Support directory access
- **Storage Location**: Uses `~/Library/Application Support/mcp-ical/` following macOS conventions

### Cross-Platform Considerations
- **EventKit**: macOS-only framework - groups implementation would need different backend on other platforms
- **Calendar Sources**: Different account types (iCloud, Google, Exchange) have varying synchronization behaviors

## Debugging Tips

### Common Issues
- **"Calendar not found"** errors usually indicate calendar was deleted from system but still referenced in groups
- **Permission errors** on first use require launching from terminal to trigger calendar access prompt
- **Empty event lists** from groups may indicate calendar synchronization delays

### Validation Utilities
The `calendar_integration.py` module includes utilities to validate group calendars and clean up invalid references automatically.