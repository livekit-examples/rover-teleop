import 'package:flutter/material.dart';
import 'package:livekit_client/livekit_client.dart' as lk;

class LiveKitController extends StatefulWidget {
  final String url;
  final String token;
  final String roomName;

  const LiveKitController({
    super.key,
    required this.url,
    required this.token,
    required this.roomName,
  });

  @override
  State<LiveKitController> createState() => _LiveKitControllerState();
}

class _LiveKitControllerState extends State<LiveKitController> {
  lk.Room? _room;
  lk.EventsListener<lk.RoomEvent>? _listener;
  bool _connecting = false;
  bool _connected = false;
  String? _errorMessage;
  List<lk.Participant> _participants = [];

  @override
  void initState() {
    super.initState();
    _connectToLiveKit();
  }

  @override
  void dispose() {
    _disconnectFromLiveKit();
    _listener?.dispose();
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
        });
        print('Disconnected from room: ${event.reason}');
      });
      
      _listener!.on<lk.ParticipantConnectedEvent>((event) {
        _updateParticipants();
        print('Participant connected: ${event.participant.identity}');
      });
      
      _listener!.on<lk.ParticipantDisconnectedEvent>((event) {
        _updateParticipants();
        print('Participant disconnected: ${event.participant.identity}');
      });

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

  Future<void> _disconnectFromLiveKit() async {
    if (_room != null) {
      await _room!.disconnect();
      _room = null;
    }
    setState(() {
      _connected = false;
      _connecting = false;
      _participants = [];
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
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        if (_connecting)
          const CircularProgressIndicator()
        else if (_connected && _room != null)
          _buildConnectedState()
        else
          _buildDisconnectedState(),
      ],
    );
  }

  Widget _buildConnectedState() {
    return Column(
      children: [
        Text('Connected to ${widget.roomName}'),
        const SizedBox(height: 16),
        ElevatedButton(
          onPressed: _disconnectFromLiveKit,
          child: const Text('Disconnect'),
        ),
        const SizedBox(height: 32),
        _buildParticipantsList(),
      ],
    );
  }

  Widget _buildDisconnectedState() {
    return Column(
      children: [
        if (_errorMessage != null)
          Padding(
            padding: const EdgeInsets.only(bottom: 16.0),
            child: Text(
              _errorMessage!,
              style: const TextStyle(color: Colors.red),
            ),
          ),
        ElevatedButton(
          onPressed: _connectToLiveKit,
          child: const Text('Connect to LiveKit'),
        ),
      ],
    );
  }

  Widget _buildParticipantsList() {
    if (_participants.isEmpty) return const Text("No participants in the room");
    
    return SizedBox(
      height: 200,
      child: ListView.builder(
        shrinkWrap: true,
        itemCount: _participants.length,
        itemBuilder: (context, index) {
          final participant = _participants[index];
          
          return ListTile(
            title: Text(participant.identity),
            subtitle: Text(participant is lk.LocalParticipant ? 'Local' : 'Remote'),
          );
        },
      ),
    );
  }
}
