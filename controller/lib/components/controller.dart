import 'dart:convert';
import 'dart:async';
import 'package:flutter/material.dart';
import 'package:livekit_client/livekit_client.dart' as lk;
import 'package:rover_controller/services/gamepad_service.dart';

class Controller extends StatefulWidget {
  final String url;
  final String token;

  const Controller({super.key, required this.url, required this.token});

  @override
  State<Controller> createState() => _ControllerState();
}

class _ControllerState extends State<Controller> {
  lk.Room? _room;
  lk.EventsListener<lk.RoomEvent>? _listener;
  bool _connecting = false;
  bool _connected = false;
  String? _errorMessage;
  List<lk.Participant> _participants = [];
  lk.VideoTrack? _roverVideoTrack;
  lk.Participant? _roverParticipant;
  final GamepadService _gamepadService = GamepadService();
  bool _sendingControls = false;
  bool _sendingAudio = false;
  lk.LocalAudioTrack? _microphoneTrack;
  Timer? _controlsTimer;

  @override
  void initState() {
    super.initState();
    _connectToLiveKit();
  }

  @override
  void dispose() {
    _disconnectFromLiveKit();
    _listener?.dispose();
    _controlsTimer?.cancel();
    _stopSendingAudio();
    super.dispose();
  }

  Future<void> _connectToLiveKit() async {
    if (_connecting || _connected) return;

    setState(() {
      _connecting = true;
      _errorMessage = null;
    });

    try {
      // Create a new room
      _room = lk.Room();

      // Set up listeners for room events
      _listener = _room!.createListener();

      _listener!.on<lk.RoomConnectedEvent>((event) {
        setState(() {
          _connected = true;
          _connecting = false;
        });
        _updateParticipants();
        print('Connected to room: ${event.room.name}');
      });

      _listener!.on<lk.RoomDisconnectedEvent>((event) {
        setState(() {
          _connected = false;
          _connecting = false;
          _participants = [];
          _roverVideoTrack = null;
          _roverParticipant = null;
          _sendingControls = false;
          _sendingAudio = false;
          _microphoneTrack = null;
        });
        print('Disconnected from room: ${event.reason}');
      });

      _listener!.on<lk.ParticipantConnectedEvent>((event) {
        _updateParticipants();
        _checkForRoverCam(event.participant);
        print('Participant connected: ${event.participant.identity}');
      });

      _listener!.on<lk.ParticipantDisconnectedEvent>((event) {
        _updateParticipants();
        if (event.participant.identity == 'rover-cam') {
          setState(() {
            _roverVideoTrack = null;
            _roverParticipant = null;
          });
        }
        print('Participant disconnected: ${event.participant.identity}');
      });

      _listener!.on<lk.TrackSubscribedEvent>((event) {
        if (event.participant.identity == 'rover-cam' &&
            event.track is lk.VideoTrack) {
          setState(() {
            _roverVideoTrack = event.track as lk.VideoTrack;
            _roverParticipant = event.participant;
          });
          print('Subscribed to rover-cam video track');

          // Start sending control data if we have a gamepad
          if (_gamepadService.isGamepadConnected.value) {
            _startSendingControlData();
          }
        }
      });

      _listener!.on<lk.TrackUnsubscribedEvent>((event) {
        if (event.participant.identity == 'rover-cam' &&
            event.track is lk.VideoTrack) {
          setState(() {
            _roverVideoTrack = null;
            _sendingControls = false;
          });
          print('Unsubscribed from rover-cam video track');
        }
      });

      print('Connecting to room: ${widget.url} with token: ${widget.token}');
      // Connect to the room
      await _room!.connect(widget.url, widget.token);
    } catch (error) {
      setState(() {
        _connecting = false;
        _connected = false;
        _errorMessage = 'Error connecting to LiveKit: $error';
      });
      print('Error connecting to LiveKit: $error');
    }
  }

  void _startSendingControlData() {
    if (_sendingControls) return;

    setState(() {
      _sendingControls = true;
    });

    // Set up a timer to send control data at 20Hz (every 50ms)
    _controlsTimer = Timer.periodic(
      const Duration(milliseconds: 50),
      (_) => _sendControls(),
    );
  }

  void _stopSendingControlData() {
    if (!_sendingControls) return;

    setState(() {
      _sendingControls = false;
    });

    _controlsTimer?.cancel();
    _controlsTimer = null;
  }

  Future<void> _startSendingAudio() async {
    if (_sendingAudio || _room == null || _room!.localParticipant == null)
      return;

    try {
      // Create microphone audio track
      _microphoneTrack = await lk.LocalAudioTrack.create();

      // Publish the audio track to the room
      await _room!.localParticipant!.publishAudioTrack(_microphoneTrack!);

      setState(() {
        _sendingAudio = true;
      });

      print('Started sending audio from microphone');
    } catch (error) {
      print('Error starting audio: $error');
      _stopSendingAudio();
    }
  }

  void _stopSendingAudio() {
    if (!_sendingAudio) return;

    try {
      if (_microphoneTrack != null) {
        // Stop the track first
        _microphoneTrack!.stop();

        // If room is connected, try to unpublish
        if (_room != null && _room!.localParticipant != null) {
          // Current version of livekit doesn't need us to manually unpublish
          // The track will be unpublished when we dispose it
        }

        // Dispose the track
        _microphoneTrack!.dispose();
        _microphoneTrack = null;
      }
    } catch (error) {
      print('Error stopping audio: $error');
    } finally {
      setState(() {
        _sendingAudio = false;
      });
    }
  }

  void _sendControls() {
    if (!_sendingControls || _room == null || _room!.localParticipant == null)
      return;

    try {
      // Get the current controller values
      final controlValues = _gamepadService.controllerValues.value;

      // Create a smaller object with just the essential joystick values
      final smallerControlData = {
        'left_x': double.parse(controlValues['leftStickX'].toStringAsFixed(3)),
        'left_y': double.parse(controlValues['leftStickY'].toStringAsFixed(3)),
        'right_x': double.parse(
          controlValues['rightStickX'].toStringAsFixed(3),
        ),
        'right_y': double.parse(
          controlValues['rightStickY'].toStringAsFixed(3),
        ),
      };

      // Create a JSON string from the smaller control data
      final controlData = {
        'type': 'gamepad',
        'data': smallerControlData,
        'timestamp': DateTime.now().millisecondsSinceEpoch,
      };

      // Convert the JSON map to a string and then to UTF-8 bytes
      final jsonString = jsonEncode(controlData);
      final dataBytes = utf8.encode(jsonString);

      // Send the control data as a List<int>
      _room!.localParticipant!.publishData(dataBytes, topic: 'controls');

      print('Sent control data: $jsonString');
    } catch (e) {
      print('Error sending control data: $e');
    }
  }

  void _sendControlData() {
    // This method is now just a wrapper for _sendControls
    _sendControls();
  }

  void _checkForRoverCam(lk.Participant participant) {
    if (participant.identity == 'rover-cam') {
      // Check if participant already has published video tracks
      for (var trackPublication in participant.trackPublications.values) {
        if (trackPublication.kind == lk.TrackType.VIDEO &&
            trackPublication.subscribed &&
            trackPublication.track != null) {
          setState(() {
            _roverVideoTrack = trackPublication.track as lk.VideoTrack;
            _roverParticipant = participant;
          });

          // Start sending control data if we have a gamepad
          if (_gamepadService.isGamepadConnected.value) {
            _startSendingControlData();
          }
          break;
        }
      }
    }
  }

  Future<void> _disconnectFromLiveKit() async {
    _stopSendingControlData();
    _stopSendingAudio();

    if (_room != null) {
      await _room!.disconnect();
      _room = null;
    }
    setState(() {
      _connected = false;
      _connecting = false;
      _participants = [];
      _roverVideoTrack = null;
      _roverParticipant = null;
    });
  }

  void _updateParticipants() {
    if (_room != null) {
      setState(() {
        _participants = [];
        if (_room!.localParticipant != null) {
          _participants.add(_room!.localParticipant!);
        }
        _participants.addAll(_room!.remoteParticipants.values);

        // Check if rover-cam is already in the room
        for (var participant in _participants) {
          _checkForRoverCam(participant);
        }
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        if (_connecting)
          _buildConnectingState()
        else if (_connected && _room != null)
          _buildConnectedState()
        else
          _buildDisconnectedState(),
      ],
    );
  }

  Widget _buildConnectedState() {
    return Stack(
      children: [
        if (_roverVideoTrack != null)
          _buildRoverVideoView()
        else
          Text(
            "Waiting for rover to connect...",
            style: Theme.of(
              context,
            ).textTheme.bodyMedium!.copyWith(color: Colors.grey),
          ),
        Positioned(top: 12, left: 12, child: _buildGamepadStatus()),
        Positioned(top: 12, right: 12, child: _buildAudioControl()),
      ],
    );
  }

  Widget _buildAudioControl() {
    return ElevatedButton(
      onPressed: _sendingAudio ? _stopSendingAudio : _startSendingAudio,
      style: ElevatedButton.styleFrom(
        backgroundColor: _sendingAudio ? Colors.red : Colors.green,
        fixedSize: const Size(130, 36),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(_sendingAudio ? Icons.mic : Icons.mic_off, size: 18),
          const SizedBox(width: 4),
          Text(
            _sendingAudio ? "Mute" : "Unmute",
            style: Theme.of(
              context,
            ).textTheme.bodyMedium!.copyWith(color: Colors.white),
          ),
        ],
      ),
    );
  }

  Widget _buildGamepadStatus() {
    return ValueListenableBuilder<bool>(
      valueListenable: _gamepadService.isGamepadConnected,
      builder: (context, isConnected, child) {
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            if (isConnected && _roverVideoTrack != null) ...[
              Column(
                children: [
                  ElevatedButton(
                    onPressed:
                        _sendingControls
                            ? _stopSendingControlData
                            : _startSendingControlData,
                    style: ElevatedButton.styleFrom(
                      backgroundColor:
                          _sendingControls ? Colors.red : Colors.green,
                      fixedSize: const Size(100, 36),
                    ),
                    child: Text(
                      _sendingControls ? "Stop" : "Start",
                      style: Theme.of(
                        context,
                      ).textTheme.bodyMedium!.copyWith(color: Colors.white),
                    ),
                  ),
                  const SizedBox(height: 12),
                  _buildJoystickVisualizer(),
                ],
              ),
            ],
          ],
        );
      },
    );
  }

  Widget _buildJoystickVisualizer() {
    return ValueListenableBuilder<Map<String, dynamic>>(
      valueListenable: _gamepadService.controllerValues,
      builder: (context, values, child) {
        final leftY = (values['leftStickY'] as num?)?.toDouble() ?? 0.0;
        final rightX = (values['rightStickX'] as num?)?.toDouble() ?? 0.0;

        return Container(
          width: 100,
          height: 100,
          decoration: BoxDecoration(
            color: Colors.black26,
            borderRadius: BorderRadius.circular(8),
          ),
          child: Stack(
            children: [
              // Vertical bar (left_y)
              Center(
                child: Container(
                  width: 10,
                  height: 80,
                  decoration: BoxDecoration(
                    color: Colors.grey.shade300,
                    borderRadius: BorderRadius.circular(5),
                  ),
                ),
              ),
              // Horizontal bar (right_x)
              Center(
                child: Container(
                  width: 80,
                  height: 10,
                  decoration: BoxDecoration(
                    color: Colors.grey.shade300,
                    borderRadius: BorderRadius.circular(5),
                  ),
                ),
              ),
              // Center dot
              Center(
                child: Container(
                  width: 10,
                  height: 10,
                  decoration: const BoxDecoration(
                    color: Colors.black38,
                    shape: BoxShape.circle,
                  ),
                ),
              ),
              // Y indicator (left_y)
              Center(
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 100),
                  transform: Matrix4.translationValues(0, -leftY * 35, 0),
                  child: Container(
                    width: 16,
                    height: 16,
                    decoration: const BoxDecoration(
                      color: Colors.blue,
                      shape: BoxShape.circle,
                    ),
                  ),
                ),
              ),
              // X indicator (right_x)
              Center(
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 100),
                  transform: Matrix4.translationValues(rightX * 35, 0, 0),
                  child: Container(
                    width: 16,
                    height: 16,
                    decoration: const BoxDecoration(
                      color: Colors.red,
                      shape: BoxShape.circle,
                    ),
                  ),
                ),
              ),
              Positioned(
                bottom: 2,
                left: 4,
                child: Text(
                  leftY.toStringAsFixed(2),
                  style: Theme.of(context).textTheme.displaySmall!.copyWith(
                    color: Colors.blue,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
              Positioned(
                bottom: 2,
                right: 4,
                child: Text(
                  rightX.toStringAsFixed(2),
                  style: Theme.of(context).textTheme.displaySmall!.copyWith(
                    color: Colors.red,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildRoverVideoView() {
    return Column(
      children: [
        SizedBox(
          height: 600,
          width: 800,
          child: lk.VideoTrackRenderer(_roverVideoTrack!),
        ),
      ],
    );
  }

  Widget _buildButtonIndicator(String label, bool isPressed) {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 4),
      width: 40,
      height: 40,
      decoration: BoxDecoration(
        color: isPressed ? Colors.blue : Colors.grey.withAlpha(77),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Center(
        child: Text(
          label,
          style: TextStyle(
            fontWeight: FontWeight.bold,
            color: isPressed ? Colors.white : Colors.black,
          ),
        ),
      ),
    );
  }

  Widget _buildDisconnectedState() {
    return Column(
      children: [
        ElevatedButton(
          onPressed: _connectToLiveKit,
          child: const Text('Connect to LiveKit'),
        ),
        Padding(
          padding: const EdgeInsets.only(top: 16.0),
          child: Text(
            _errorMessage ?? '',
            style: Theme.of(
              context,
            ).textTheme.bodyMedium!.copyWith(color: Colors.red),
          ),
        ),
      ],
    );
  }

  Widget _buildConnectingState() {
    return Column(
      children: [
        const CircularProgressIndicator(),
        Padding(
          padding: const EdgeInsets.only(top: 16.0),
          child: Text(
            'Connecting to LiveKit...',
            style: Theme.of(
              context,
            ).textTheme.bodyMedium!.copyWith(color: Colors.grey),
          ),
        ),
      ],
    );
  }
}
