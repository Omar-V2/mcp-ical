# MCP iCal Server Installation Guide

## Quick Installation

1. **Clone and Setup**

    ```bash
    # Clone the repository
    git clone https://github.com/Omar-V2/mcp-ical.git
    cd mcp-ical

    # Install dependencies
    uv sync
    ```

2. **Configure Claude for Desktop**

    Create or edit `~/Library/Application\ Support/Claude/claude_desktop_config.json`:

    ```json
    {
        "mcpServers": {
            "mcp-ical": {
                "command": "uv"
                "args": [
                    "--directory"
                    "/ABSOLUTE/PATH/TO/PARENT/FOLDER/mcp-ical"
                    "run"
                    "mcp-ical"
                ]
            }
        }
    }
    ```

## Calendar Access Configuration

macOS Calendar Service access is required for the MCP iCal server to function properly. Follow one of the methods below to grant calendar access to your Terminal app or to Claude.

### Method 1: Launch Claude from Terminal (Quick)

> ⚠️ **Critical**: Claude must be launched from the terminal to properly request calendar permissions. Launching directly from Finder will not trigger the permissions prompt.

Run the following command in your terminal:

```bash
/Applications/Claude.app/Contents/MacOS/Claude
```

When you first use a calendar-related command, macOS will prompt for calendar access. This prompt will only appear if you launched Claude from the terminal as specified above.

### Method 1B: Alfred Workflow (Recommended)

For a more convenient and powerful launch experience, see our [Alfred Setup Guide](alfred-setup.md). This method:

- Provides a quick keyword-based launch (`cld`)
- Supports running multiple Claude instances simultaneously
- Ensures proper calendar permission prompts through Alfred
- Offers a cleaner workflow for daily use

### Method 2: Manually Grant Calendar Access

> ⚠️ **WARNING**: This method modifies the TCC database directly, which is not recommended by Apple. Use at your own risk.
>
> ⚠️ **CRITICAL WARNING**: Modifying the TCC database directly can potentially cause system instability or security issues. This is an unofficial method that bypasses Apple's permission system, and future macOS updates may change how permissions work. Always back up your TCC database before making changes (as shown below) and proceed at your own risk. If something goes wrong, you may need to reset all TCC permissions or restore from a backup.

This method has been tested on macOS 15.4 and requires full-disk access for your terminal emulator.

```bash
# Backup TCC database to your desktop
# This is a critical step! Always backup your TCC database before making changes.
cp ~/Library/Application\ Support/com.apple.TCC/TCC.db ~/Desktop/TCC_backup.db

# Grant Calendar access to Claude
# This command modifies the TCC database to allow access for the specified bundle identifier.
sqlite3 ~/Library/Application\ Support/com.apple.TCC/TCC.db <<EOF
REPLACE INTO access
VALUES(
    'kTCCServiceCalendar',
    'com.anthropic.claudefordesktop',
    0,
    2,
    2,
    2,
    NULL,
    NULL,
    0,
    'UNUSED',
    NULL,
    16,
    CAST(strftime('%s''now') AS INTEGER),
    NULL,
    NULL,
    'UNUSED',
    0
);
EOF
```

After allowing `com.anthropic.claudefordesktop` access to the Calendar service, you can reopen Claude.app as you normally would.

### Reverting Calendar Permissions

If you want to revert the changes you made to the TCC database, you can use macOS's built-in `tccutil` command to reset the Calendar permissions for Claude:

```bash
# Reset Calendar permissions for Claude
tccutil reset Calendar com.anthropic.claudefordesktop
```

## Usage

Once installed and configured with proper calendar access, you can start using the MCP iCal server:

Try: `What's my schedule looking like for next week?`
