# MCP iCal Server

<div align="center">

🗓️ Natural Language Calendar Management for macOS

[![MIT License](https://img.shields.io/badge/License-MIT-green.svg)](https://choosealicense.com/licenses/mit/)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![MCP Compatible](https://img.shields.io/badge/MCP-Compatible-purple.svg)](https://modelcontextprotocol.io)

</div>

## 🌟 Overview

Transform how you interact with your macOS calendar using natural language! The mcp-ical server leverages the Model Context Protocol (MCP) to turn your calendar management into a conversational experience.

```bash
You: "What's my schedule for next week?"
Claude: "Let me check that for you..."
[Displays a clean overview of your upcoming week]

You: "Add a lunch meeting with Sarah tomorrow at noon"
Claude: "✨ 📅 Created: Lunch with Sarah Tomorrow, 12:00 PM"
```

## ✨ Features

### 📁 Calendar Groups ✨ NEW!

Organize calendars from different sources (iCloud, Google, Office365) into logical collections for streamlined management!

```text
"Create a Work group with my Office365 and Google work calendars"
↓
📂 Created: Work Group
   📅 Office365 Calendar
   📅 Google Work Calendar

"What meetings do I have in my Work calendars this week?"
↓
📊 Shows events from all calendars in your Work group
```

#### Calendar Groups Features

- **Cross-Account Support**: Group calendars from different sources (iCloud, Google, Exchange, etc.)
- **Persistent Storage**: Groups persist between app launches with local JSON storage
- **Natural Language Queries**: "Show me events from Family calendars next month"
- **Complete CRUD Operations**: Create, update, delete, and list calendar groups
- **Flexible Management**: Add/remove individual calendars from existing groups

#### Calendar Groups Examples

```text
📂 Group Management:
"Create group 'Fitness' with my Gym and Sports calendars"
"Add my Project calendar to the Work group"
"Remove Personal calendar from the Work group"

📅 Group-Based Scheduling:
"What's my schedule in Family calendars this weekend?"
"Show me all Work events for next week"
"List events from my Fitness group today"

🔧 Group Operations:
"List all my calendar groups"
"Show me what calendars are in my Work group"
"Delete the Old Projects group"
```

### 📅 Event Creation

Transform natural language into calendar events instantly!

```text
"Schedule a team lunch next Thursday at 1 PM at Bistro Garden"
↓
📎 Created: Team Lunch
   📅 Thursday, 1:00 PM
   📍 Bistro Garden
```

#### Supported Features

- Custom calendar selection
- Location and notes
- Smart reminders
- Recurring events

#### Power User Examples

```text
🔄 Recurring Events:
"Set up my weekly team sync every Monday at 9 AM with a 15-minute reminder"

📝 Detailed Events:
"Schedule a product review meeting tomorrow from 2-4 PM in the Engineering calendar, 
add notes about reviewing Q1 metrics, and remind me 1 hour before"

📱 Multi-Calendar Support:
"Add a dentist appointment to my Personal calendar for next Wednesday at 3 PM"
```

### 🔍 Smart Schedule Management & Availability

Quick access to your schedule with natural queries:

```text
"What's on my calendar for next week?"
↓
📊 Shows your upcoming events with smart formatting

"When am I free to schedule a 2-hour meeting next Tuesday?"
↓
🕒 Available time slots found:
   • Tuesday 10:00 AM - 12:00 PM
   • Tuesday 2:00 PM - 4:00 PM
```

### ✏️ Intelligent Event Updates

Modify events naturally:

```text
Before: "Move tomorrow's team meeting to 3 PM instead"
↓
After: ✨ Meeting rescheduled to 3:00 PM
```

#### Update Capabilities

- Time and date modifications
- Calendar transfers
- Location updates
- Note additions
- Reminder adjustments
- Recurring pattern changes

### 📊 Calendar Management

- **Enhanced Calendar Listing**: View calendars organized by account with highlighted default calendar
- **Calendar Groups**: Organize calendars into logical collections across all sources
- **Smart Calendar Suggestions**: Intelligent recommendations based on context
- **Seamless Multi-Account Support**: Works with iCloud, Google, Office365, Exchange, and more

> 💡 **Pro Tip**: Since you can create events in custom calendars, if you have your Google Calendar synced with your iCloud Calendar, you can use this MCP server to create events in your Google Calendar too! Just specify the Google calendar when creating/updating events.

## 🚀 Quick Start

> 💡 **Note**: While these instructions focus on setting up the MCP server with Claude for Desktop, this server can be used with any MCP-compatible client. For more details on using different clients, see [the MCP documentation](https://modelcontextprotocol.io/quickstart/client).

### Prerequisites

- [uv package manager](https://github.com/astral-sh/uv)
- macOS with Calendar app configured
- An MCP client - [Claude for desktop](https://claude.ai/download) is recommended

### Installation

Whilst this MCP server can be used with any MCP compatible client, the instructions below are for use with Claude for desktop.

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
                "command": "uv",
                "args": [
                    "--directory",
                    "/ABSOLUTE/PATH/TO/PARENT/FOLDER/mcp-ical",
                    "run",
                    "mcp-ical"
                ]
            }
        }
    }
    ```

3. **Launch Claude for Calendar Access**

    > ⚠️ **Critical**: Claude must be launched from the terminal to properly request calendar permissions. Launching directly from Finder will not trigger the permissions prompt.

    **Option A: Terminal Launch (Quick)**
    ```bash
    /Applications/Claude.app/Contents/MacOS/Claude
    ```

    **Option B: Alfred Workflow (Recommended)**
    
    For a more convenient launch experience that supports multiple Claude instances, see our [Alfred Setup Guide](docs/alfred-setup.md).

    > ⚠️ **Warning**: Alternatively, you can [manually grant calendar access](docs/install.md#method-2-manually-grant-calendar-access), but this involves modifying system files and should only be done if you understand the risks involved.

4. **Start Using!**

    ```text
    Try: "What's my schedule looking like for next week?"
    ```

> 🔑 **Note**: When you first use a calendar-related command, macOS will prompt for calendar access. This prompt will only appear if you launched Claude from the terminal as specified above.

## 🧪 Testing

> ⚠️ **Warning**: Tests will create temporary calendars and events. While cleanup is automatic, only run tests in development environments.

```bash
# Install dev dependencies
uv sync --dev

# Run test suite
uv run pytest tests
```

## 🐛 Known Issues

### Recurring Events

- Non-standard recurring schedules may not always be set correctly
- Better results with Claude 3.5 Sonnet compared to Haiku
- Reminder timing for recurring all-day events may be off by one day

## 🤝 Contributing

Feedback and contributions are welcome. Here's how you can help:

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built with [Model Context Protocol](https://modelcontextprotocol.io)
- macOS Calendar integration built with [PyObjC](https://github.com/ronaldoussoren/pyobjc)
