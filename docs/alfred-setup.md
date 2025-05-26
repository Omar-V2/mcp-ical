# Setting up Alfred Launcher for Claude Desktop

This method allows you to launch Claude Desktop from Alfred while properly triggering macOS calendar permission prompts.

## Step-by-Step Alfred Workflow Setup

### 1. Create a New Workflow

1. **Open Alfred Preferences**
   - Press `Cmd + ,` while Alfred is active, or
   - Click the Alfred icon in your menu bar and select "Preferences"

2. **Navigate to Workflows**
   - Click on the "Workflows" tab in the left sidebar

3. **Create New Workflow**
   - Click the "+" button at the bottom of the workflows list
   - Select "Blank Workflow" from the dropdown menu
   - Give your workflow a name (e.g., "Launch Claude Desktop")

### 2. Add the Keyword Input

1. **Add Keyword Component**
   - In the empty workflow canvas, click the "+" button
   - Select "Inputs" → "Keyword"

2. **Configure the Keyword**
   - **Keyword**: `cld` (or your preferred trigger)
   - **Title**: `Launch Claude Desktop`
   - **Subtitle**: `Start Claude with calendar access`
   - **Argument**: Select "No Argument" (this is important!)

3. **Add Claude Icon (Optional)**
   - Click on the keyword box you just created
   - In the top-right corner, click on the icon placeholder
   - Navigate to `/Applications/Claude.app` and select it
   - Alfred will extract and use Claude's app icon for your workflow

### 4. Connect to Run Script Action

1. **Add Run Script Action**
   - Click on the small connector dot on the right side of your keyword box
   - Drag to create a connection, then select "Actions" → "Run Script"

2. **Configure the Script**
   - **Language**: `/bin/bash`
   - **Script**: 
   ```bash
   /Applications/Claude.app/Contents/MacOS/Claude > /dev/null 2>&1 &
   ```
   - The `> /dev/null 2>&1 &` part runs Claude in the background without cluttering your terminal

### 5. Test and Save

1. **Save the Workflow**
   - Press `Cmd + S` or the workflow will auto-save

2. **Test the Setup**
   - Press `Cmd + Space` to open Alfred
   - Type `cld` and press Enter
   - Claude should launch properly

## Important Notes

- **Permission Prompt**: When you first use a calendar-related MCP command, **Alfred will be asked to grant calendar access** (not Claude directly)
- **No Arguments**: Make sure the keyword is set to "No Argument" - this prevents Alfred from waiting for additional input
- **Background Process**: The `&` at the end of the script ensures Claude runs independently of Alfred
- **Multiple Instances**: This method allows you to run multiple Claude Desktop instances simultaneously, each with full MCP support. Simply trigger the Alfred workflow multiple times to launch additional instances for parallel work sessions.

## Troubleshooting

If Claude doesn't launch:
- Verify the path `/Applications/Claude.app/Contents/MacOS/Claude` exists
- Try running the command directly in Terminal first to ensure it works
- Check that Alfred has the necessary permissions in System Preferences → Security & Privacy

## Alternative Script Options

If you prefer Claude to launch with a visible terminal window:
```bash
osascript -e 'tell application "Terminal" to do script "/Applications/Claude.app/Contents/MacOS/Claude"'
```

For a cleaner launch without terminal output:
```bash
nohup /Applications/Claude.app/Contents/MacOS/Claude >/dev/null 2>&1 &
```

This Alfred workflow provides a much safer and more user-friendly alternative to modifying the TCC database, while still ensuring proper calendar access permissions are requested.