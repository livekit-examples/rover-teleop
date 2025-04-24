# Rover Teleop Controller

This Flutter application connects to a LiveKit server to control and view a rover's camera feed.

## Setup

1. Create a `.env` file in the root directory with the following variables:

```
LIVEKIT_URL=wss://your-livekit-server.com
LIVEKIT_TOKEN=your-livekit-token
LIVEKIT_ROOM=your-room-name
```

2. Install dependencies:

```bash
flutter pub get
```

3. Run the application:

```bash
flutter run
```

## Usage

The app will automatically connect to the LiveKit server using the credentials from the `.env` file.

- The main screen displays the rover camera feed when connected
- Tap the settings icon in the app bar to access the configuration screen
- The configuration screen allows you to modify connection parameters

## Requirements

- Flutter 3.7.2 or higher
- A valid LiveKit server and token
