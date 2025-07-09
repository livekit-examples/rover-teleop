#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
#   "livekit",
#   "python-dotenv",
#   "asyncio",
# ]
# ///

import os
import json
import asyncio
import argparse
from dotenv import load_dotenv
from livekit import rtc

load_dotenv()

async def send_autonomy_command(token: str, livekit_url: str, cmd_type: str, 
                               distance: float, velocity: float, steering: float):
    """Send autonomy command to LiveKit room."""
    
    # Create the command data structure
    command_data = {
        "type": cmd_type,
        "distance": distance,
        "velocity": velocity,
        "steering": steering
    }
    
    print(f"Sending command: {command_data}")
    
    # Create room and connect
    loop = asyncio.get_event_loop()
    room = rtc.Room(loop=loop)
    
    try:
        # Connect to the room using the provided token
        await room.connect(livekit_url, token)
        print(f"Connected to room: {room.name}")
        
        # Wait a moment for connection to stabilize
        await asyncio.sleep(1)
        
        # Publish the command data to the "command" topic
        await room.local_participant.publish_data(
            json.dumps(command_data).encode(),
            topic="command",
            reliable=True
        )
        
        print("Command sent successfully!")
        
        # Wait a moment before disconnecting
        await asyncio.sleep(1)
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        # Disconnect from the room
        await room.disconnect()
        print("Disconnected from room")

def main():
    parser = argparse.ArgumentParser(description="Send autonomy command to rover via LiveKit")
    
    # Required arguments
    parser.add_argument("token", help="LiveKit token for authentication")
    parser.add_argument("type", choices=["forward", "backward"], 
                       help="Movement type: forward or backward")
    parser.add_argument("distance", type=float, help="Distance to travel in meters")
    parser.add_argument("velocity", type=float, help="Velocity in meters per second")
    parser.add_argument("steering", type=float, help="Steering value (-1.0 to 1.0)")
    
    # Optional argument for LiveKit URL
    parser.add_argument("--url", default=os.environ.get("LIVEKIT_URL"), 
                       help="LiveKit server URL (default: from LIVEKIT_URL env var)")
    
    args = parser.parse_args()
    
    # Validate arguments
    if not args.url:
        print("Error: LiveKit URL must be provided via --url or LIVEKIT_URL environment variable")
        return
    
    if args.distance <= 0:
        print("Error: Distance must be greater than 0")
        return
    
    if args.velocity <= 0:
        print("Error: Velocity must be greater than 0")
        return
    
    if args.steering < -1.0 or args.steering > 1.0:
        print("Error: Steering must be between -1.0 and 1.0")
        return
    
    # Run the async function
    asyncio.run(send_autonomy_command(
        args.token, 
        args.url, 
        args.type, 
        args.distance, 
        args.velocity, 
        args.steering
    ))

if __name__ == "__main__":
    main() 