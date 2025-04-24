import 'package:flutter/material.dart';
import 'controller.dart';

class LiveKitExample extends StatefulWidget {
  const LiveKitExample({super.key});

  @override
  State<LiveKitExample> createState() => _LiveKitExampleState();
}

class _LiveKitExampleState extends State<LiveKitExample> {
  final _urlController = TextEditingController();
  final _tokenController = TextEditingController();
  final _roomNameController = TextEditingController();
  bool _showController = false;

  @override
  void initState() {
    super.initState();
    // Set default values (you would want to replace these with your actual values)
    _urlController.text = 'wss://your-livekit-server.com';
    _tokenController.text = 'your-token';
    _roomNameController.text = 'your-room-name';
  }

  @override
  void dispose() {
    _urlController.dispose();
    _tokenController.dispose();
    _roomNameController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('LiveKit Example'),
      ),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: _showController
            ? SizedBox(
                height: MediaQuery.of(context).size.height - 100,
                child: LiveKitController(
                  url: _urlController.text,
                  token: _tokenController.text,
                  roomName: _roomNameController.text,
                ),
              )
            : Column(
                children: [
                  TextField(
                    controller: _urlController,
                    decoration: const InputDecoration(
                      labelText: 'LiveKit Server URL',
                      hintText: 'wss://your-livekit-server.com',
                    ),
                  ),
                  const SizedBox(height: 16),
                  TextField(
                    controller: _tokenController,
                    decoration: const InputDecoration(
                      labelText: 'LiveKit Token',
                      hintText: 'Your LiveKit token',
                    ),
                  ),
                  const SizedBox(height: 16),
                  TextField(
                    controller: _roomNameController,
                    decoration: const InputDecoration(
                      labelText: 'Room Name',
                      hintText: 'Enter room name',
                    ),
                  ),
                  const SizedBox(height: 32),
                  ElevatedButton(
                    onPressed: () {
                      if (_urlController.text.isNotEmpty &&
                          _tokenController.text.isNotEmpty &&
                          _roomNameController.text.isNotEmpty) {
                        setState(() {
                          _showController = true;
                        });
                      }
                    },
                    child: const Text('Connect to LiveKit'),
                  ),
                ],
              ),
      ),
      floatingActionButton: _showController
          ? FloatingActionButton(
              onPressed: () {
                setState(() {
                  _showController = false;
                });
              },
              child: const Icon(Icons.arrow_back),
            )
          : null,
    );
  }
} 