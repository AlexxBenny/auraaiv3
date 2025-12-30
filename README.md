# 🤖 AURA - Advanced Neural Network Interface

A secure, modular AI assistant with a futuristic GUI that learns and adapts to new tasks through natural language commands. AURA can control Windows systems, learn new capabilities, and improve itself over time through its neural network architecture.

## ✨ Features

### 🧠 Self-Improvement
- **Dynamic Learning**: Automatically generates new functions when encountering unknown tasks
- **Capability Expansion**: Learns from failures and adds new capabilities to its toolkit
- **Success Tracking**: Monitors performance and optimizes based on usage patterns
- **Persistent Memory**: Remembers learned capabilities across sessions

### 🔒 Security
- **Code Validation**: AST-based security validation before code execution
- **Sandboxed Execution**: Safe code execution with timeout and resource limits
- **API Key Protection**: Secure environment variable-based API key management
- **Function Whitelisting**: Only allows approved modules and functions

### 🎤 Multi-Modal Interface
- **Voice Commands**: Natural speech recognition and text-to-speech responses
- **Text Interface**: Traditional keyboard input for precise commands
- **Dynamic Switching**: Switch between voice and text modes during operation

### 🖥️ Windows System Control
- Desktop icon visibility control
- System volume management
- File Explorer operations
- Workstation locking
- Wallpaper changes
- Network adapter control
- And much more...

## 🚀 Quick Start

### Prerequisites
- Python 3.8 or higher
- Windows 10/11 (for system control features)
- OpenRouter API key (get one at [openrouter.ai](https://openrouter.ai/))

### Installation

1. **Clone or download the project**
2. **Run the setup script**:
   ```bash
   python setup.py
   ```
   This will:
   - Install required dependencies
   - Help you set up your API key
   - Run tests to verify installation
   - Create a desktop shortcut (optional)

3. **Set your API key** (if not done during setup):
   ```bash
   # Windows
   set OPENROUTER_API_KEY=your_key_here
   
   # Linux/Mac
   export OPENROUTER_API_KEY=your_key_here
   ```

4. **Start AURA**:
   ```bash
   # Launch AURA GUI directly
   python aura_gui.py
   
   # Or use the batch file for full experience
   start_aura.bat
   ```

## 📖 Usage

### Basic Commands
The assistant understands natural language commands:

```
"open notepad"
"hide desktop icons"
"mute system volume"
"change wallpaper"
"lock workstation"
"open file explorer"
```

### Special Commands
- `status` - Show system status and statistics
- `capabilities` - List all learned capabilities
- `learning` - Show learning information and suggestions
- `switch to voice/text` - Change input mode
- `help` - Show available commands
- `exit` or `quit` - Stop the assistant

### Self-Improvement in Action

When you ask the assistant to do something it doesn't know how to do:

1. **First Attempt**: It tries with existing knowledge
2. **Failure Detection**: Recognizes when it lacks capability
3. **Learning Phase**: Generates new function to handle the task
4. **Integration**: Adds the new capability to its toolkit
5. **Retry**: Attempts the original command with new capability
6. **Success**: Task completed and capability saved for future use

Example:
```
You: "Take a screenshot"
Assistant: ❌ Execution failed
Assistant: 🔄 Attempting to self-improve...
Assistant: ✅ Successfully added take_screenshot() capability
Assistant: 🔄 Retrying with new capability...
Assistant: ✅ Task completed successfully!
```

## 🏗️ Architecture

### Core Components

- **`assistant.py`** - Main application and coordination
- **`config.py`** - Secure configuration management
- **`ai_client.py`** - Modern OpenAI API client
- **`code_executor.py`** - Safe code execution with validation
- **`capability_manager.py`** - Dynamic capability management
- **`self_improvement.py`** - Self-improvement engine
- **`voice_interface.py`** - Voice and text interfaces
- **`windows_system_utils.py`** - Windows system functions

### Data Storage

The assistant stores its learning data in:
- `~/.ai_assistant/config.json` - Configuration settings
- `~/.ai_assistant/capabilities.json` - Learned capabilities
- `~/.ai_assistant/learning_data.json` - Learning history and statistics
- `~/.ai_assistant/logs/` - Application logs

## 🔧 Configuration

### Environment Variables
- `OPENROUTER_API_KEY` - Your OpenRouter API key (required)
- `OPENAI_API_KEY` - Alternative API key (fallback)

### Configuration File
Edit `~/.ai_assistant/config.json` to customize:

```json
{
  "api": {
    "model": "google/gemini-2.0-flash-001",
    "base_url": "https://openrouter.ai/api/v1"
  },
  "security": {
    "max_code_length": 5000,
    "execution_timeout": 30
  },
  "learning": {
    "auto_improve": true,
    "max_learning_history": 1000
  }
}
```

## 🛡️ Security Features

### Code Validation
- AST parsing to detect malicious code patterns
- Whitelist of allowed modules and functions
- Blacklist of dangerous operations
- Code length and complexity limits

### Execution Safety
- Sandboxed execution environment
- Timeout protection
- Resource usage monitoring
- Rollback capabilities

### API Security
- Environment variable-based key storage
- No hardcoded credentials
- Secure API communication

## 🧪 Testing

Run the test suite:
```bash
python -m pytest tests/
```

Or run basic validation:
```bash
python setup.py
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure security validation passes
5. Submit a pull request

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## ⚠️ Disclaimer

This assistant can execute code and modify system settings. While security measures are in place:

- Always review generated code before execution
- Use in a controlled environment
- Keep backups of important data
- Monitor system changes

The assistant is designed to be helpful but should be used responsibly.

## 🆘 Troubleshooting

### Common Issues

**"No API key found"**
- Set the `OPENROUTER_API_KEY` environment variable
- Restart your terminal/IDE after setting the variable

**"Voice libraries not available"**
- Install audio dependencies: `pip install pyaudio`
- On Windows, you may need Visual C++ build tools

**"Permission denied" errors**
- Run as administrator for system-level operations
- Check Windows UAC settings

**Code execution fails**
- Check the logs in `~/.ai_assistant/logs/`
- Verify the generated code in the console output
- Try switching to text mode for debugging

### Getting Help

1. Check the logs in `~/.ai_assistant/logs/assistant.log`
2. Use the `status` command to check system health
3. Try the `help` command for available options
4. Review the generated code for issues

## 🔮 Future Enhancements

- Cross-platform support (Linux, macOS)
- Plugin system for custom capabilities
- Web interface for remote control
- Integration with more AI models
- Advanced learning algorithms
- Collaborative learning between instances
