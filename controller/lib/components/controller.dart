import 'dart:convert';
import 'dart:async';
import 'package:flutter/material.dart';
import 'package:livekit_client/livekit_client.dart' as lk;
import 'package:rover_controller/services/gamepad_service.dart';

class Controller extends StatefulWidget {
  final String url;
  final String token;

  const Controller({
    super.key,
    required this.url,
    required this.token,
  });

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
      await _room!.connect(
        widget.url, 
        widget.token,
      );
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
    _controlsTimer = Timer.periodic(const Duration(milliseconds: 50), (_) => _sendControls());
  }
  
  void _stopSendingControlData() {
    if (!_sendingControls) return;
    
    setState(() {
      _sendingControls = false;
    });
    
    _controlsTimer?.cancel();
    _controlsTimer = null;
  }
  
  void _sendControls() {
    if (!_sendingControls || _room == null || _room!.localParticipant == null) return;
    
    try {
      // Get the current controller values
      final controlValues = _gamepadService.controllerValues.value;
      
      // Create a smaller object with just the essential joystick values
      final smallerControlData = {
        'left_x': double.parse(controlValues['leftStickX'].toStringAsFixed(3)),
        'left_y': double.parse(controlValues['leftStickY'].toStringAsFixed(3)),
        'right_x': double.parse(controlValues['rightStickX'].toStringAsFixed(3)),
        'right_y': double.parse(controlValues['rightStickY'].toStringAsFixed(3))
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
          const Text("Waiting for rover-cam video..."),
        Positioned(
          top: 12,
          left: 12,
          child: _buildGamepadStatus(),
        ),
      ],
    );
  }

  Widget _buildGamepadStatus() {
    return ValueListenableBuilder<bool>(
      valueListenable: _gamepadService.isGamepadConnected,
      builder: (context, isConnected, child) {
        return Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (isConnected && _roverVideoTrack != null) ...[
              ElevatedButton(
                onPressed: _sendingControls ? _stopSendingControlData : _startSendingControlData,
                style: ElevatedButton.styleFrom(
                  backgroundColor: _sendingControls ? Colors.red : Colors.green,
                ),
                child: Text(_sendingControls ? "Stop Teleop" : "Start Teleop", style: Theme.of(context).textTheme.bodyMedium!.copyWith(color: Colors.white),),
              ),
            ],
          ],
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
          child: lk.VideoTrackRenderer(
            _roverVideoTrack!,
          ),
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
            style: Theme.of(context).textTheme.bodyMedium!.copyWith(color: Colors.red),
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
            style: Theme.of(context).textTheme.bodyMedium!.copyWith(color: Colors.grey),
          ),
        ),
      ],
    );
  }
}
