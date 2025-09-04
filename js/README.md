# Google Meet Recorder

A Node.js application for recording Google Meet sessions with audio streaming and chat monitoring capabilities.

## 📁 Project Structure

```
google-meet-recorder/
├── src/
│   ├── config/
│   │   └── index.js              # Configuration and constants
│   ├── utils/
│   │   └── index.js              # Utility functions
│   ├── browser/
│   │   └── manager.js            # Browser launch and management
│   ├── auth/
│   │   ├── handler.js            # Authentication logic
│   │   └── firstLogin.js         # First login wrapper
│   ├── meet/
│   │   ├── audio/
│   │   │   └── manager.js        # Audio management
│   │   ├── ui/
│   │   │   └── manager.js        # Meet UI interactions
│   │   └── recorder.js           # Main recording logic
│   ├── monitoring/
│   │   └── index.js              # Speaker tracking & monitoring
│   ├── stream/
│   │   └── manager.js            # WebSocket & stream management
│   ├── managers/
│   │   └── session.js            # Session management
│   └── api/
│       └── server.js             # Express server
├── index.js                      # Main entry point
├── server.js                     # Server entry (backwards compatibility)
├── package.json                  # Dependencies and scripts
└── README.md                     # Documentation
```

## 🚀 Installation

```bash
npm install
```

## 🏃‍♂️ Usage

### Start the server
```bash
npm start
# or
npm run start:api
```

## 📡 API Endpoints

### Login (with 2FA)
```bash
POST /login
Content-Type: application/json

{
  "email": "your-email@gmail.com",
  "password": "your-password",
  "phone": "+1234567890"
}
```

### Submit 2FA Code
```bash
POST /submit-2fa
Content-Type: application/json

{
  "code": "123456"
}
```

### Start Recording Session
```bash
POST /start
Content-Type: application/json

{
  "email": "your-email@gmail.com",
  "password": "your-password",
  "meetCode": "abc-defg-hij",
  "port": 8080,
  "chatPort": 8081
}
```

### Terminate Session
```bash
POST /terminate
Content-Type: application/json

{
  "sessionId": "session-uuid"
}
```

### List Active Sessions
```bash
GET /list
```

## 🏗️ Architecture

### Core Modules

- **`src/config/`** - Configuration constants, browser settings, URLs
- **`src/utils/`** - Common utilities (sleep, logging, file operations)
- **`src/browser/`** - Browser launching and permission management
- **`src/auth/`** - Google authentication flow including 2FA

### Meet Functionality

- **`src/meet/ui/`** - Google Meet UI interactions (navigation, chat, participants)
- **`src/meet/audio/`** - Audio management and keepalive functionality
- **`src/monitoring/`** - Speaker tracking, chat monitoring, periodic screenshots
- **`src/stream/`** - WebSocket connections and audio streaming

### Application Layer

- **`src/meet/recorder.js`** - Main orchestrator for Meet recording
- **`src/managers/session.js`** - Multi-session management
- **`src/api/server.js`** - Express server with REST endpoints

## ✨ Features

- **🎵 Audio Streaming** - Real-time audio streaming via WebSocket
- **💬 Chat Monitoring** - Live chat message tracking and forwarding
- **🎤 Speaker Tracking** - Real-time speaker identification
- **🔄 Session Management** - Support for multiple concurrent sessions
- **📸 Screenshot Logging** - Automatic screenshots for debugging
- **🔐 2FA Support** - Google 2-factor authentication handling
- **🧩 Modular Architecture** - Clean, maintainable code structure

## 📦 Dependencies

- **puppeteer** - Browser automation
- **puppeteer-extra** - Enhanced Puppeteer with plugins
- **puppeteer-stream** - Audio/video streaming from browser
- **express** - Web server framework
- **ws** - WebSocket library
- **uuid** - Session ID generation

## ⚙️ Configuration

Configuration is centralized in `src/config/index.js`:

- Browser launch arguments
- Google service URLs
- WebSocket intervals
- UI element selectors
- Permission settings

## 📝 Notes

- Screenshots are automatically saved to `js/screenshots/` directory
- Login screenshots go to `js/screenshots/login/` subdirectory
- The application requires a display environment (not headless by default)
- Audio streaming uses WebM format with Opus codec
- Supports multiple concurrent recording sessions

## 🔧 Development

The modular structure makes it easy to:

- **Modify components** independently
- **Add new features** in appropriate modules
- **Test** individual components
- **Scale** the application
- **Maintain** clean code organization

Each module has a specific responsibility and clear interfaces, making the codebase maintainable and extensible.