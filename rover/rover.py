# /// script
# dependencies = [
#   "livekit",
#   "livekit_api",
#   "pyserial",
#   "python-dotenv",
#   "asyncio",
# ]
# ///

import os
import logging
import asyncio
import json
import serial
from dotenv import load_dotenv
from signal import SIGINT, SIGTERM
from livekit import rtc
from auth import generate_token

load_dotenv()
# ensure LIVEKIT_URL, LIVEKIT_API_KEY, and LIVEKIT_API_SECRET are set in your .env file
LIVEKIT_URL = os.environ.get("LIVEKIT_URL")
ROOM_NAME = os.environ.get("ROOM_NAME")
ROVER_PORT = os.environ.get("ROVER_PORT")

async def main(room: rtc.Room):
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    # Try to connect to serial port, but continue even if failed
    ser = None
    try:
        # Use the environment variable for port or default to a common port
        if not ROVER_PORT:
            logger.info("ROVER_PORT environment variable not set, defaulting to /dev/ttyUSB0")
            port = '/dev/ttyUSB0'
        else:
            port = ROVER_PORT
            
        # Create serial connection with 115200 baud rate using standard serial library
        ser = serial.Serial(port, 115200, timeout=1)
        logger.info(f"Successfully connected to serial port {port} at 115200 baud")
    except Exception as e:
        logger.warning(f"Failed to connect to serial port: {e}")
        logger.info("Continuing without serial connection - will only log received data")
        ser = None

    # handler for receiving data packet
    @room.on("data_received")
    def on_data_received(data: rtc.DataPacket):
        logger.info("Received data from %s topic: %s", data.participant.identity, data.topic)
        try:
            # Decode and parse the data
            decoded_data = data.data.decode('utf-8')
            
            # Try to parse as JSON
            json_data = json.loads(decoded_data)
            
            # First validate that data is of type 'gamepad'
            if not json_data.get('type') == 'gamepad':
                logger.info("Received data is not of type 'gamepad', ignoring")
                return
                
            # Get the gamepad data
            gamepad_data = json_data.get('data', {})
            
            # Check if we have the expected thumbstick values
            if all(k in gamepad_data for k in ["left_x", "left_y", "right_x", "right_y"]):
                # Get the throttle (left_y) and steering (right_x) values
                # Gamepad values are typically in range [-1, 1]
                throttle = float(gamepad_data['left_y'])
                steering = float(gamepad_data['right_x'])
                
                # Scale throttle to [-0.5, 0.5] range
                throttle_scaled = round(throttle * 0.5, 3)
                
                # Calculate left and right motor values based on throttle and steering
                # When steering is 0, both motors get the same value
                # When steering is to the right (positive), reduce left motor value
                # When steering is to the left (negative), reduce right motor value
                if throttle_scaled > 0:
                    left_motor = throttle_scaled + (steering * abs(throttle_scaled))
                    right_motor = throttle_scaled - (steering * abs(throttle_scaled))
                else:
                    left_motor = throttle_scaled - (steering * abs(throttle_scaled))
                    right_motor = throttle_scaled + (steering * abs(throttle_scaled))
                
                # Ensure values stay within the valid range [-0.5, 0.5]
                left_motor = max(min(left_motor, 0.5), -0.5)
                right_motor = max(min(right_motor, 0.5), -0.5)
                
                # Round to 3 decimal places
                left_motor = round(left_motor, 3)
                right_motor = round(right_motor, 3)
                
                # Create command JSON as specified
                command_data = {
                    "T": 1,  # Type 1 for motor control
                    "L": left_motor,
                    "R": right_motor
                }
                print(f"command_data: {command_data}")
                # Convert to JSON string
                command_json = json.dumps(command_data)
                
                # Forward to serial port if connection is available
                if ser and ser.is_open:
                    # Add newline for serial transmission
                    serial_command = command_json + "\n"
                    ser.write(serial_command.encode())
                    logger.info(f"Successfully sent to serial port: {command_json}")
                else:
                    logger.info("Serial connection not available - data logged but not sent")
            else:
                logger.info("Received data does not contain expected thumbstick values")
                
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            logger.error(f"Error decoding/parsing data: {e}")
        except Exception as e:
            logger.error(f"Error processing data: {e}")

    token = generate_token(ROOM_NAME, "rover", "Rover Receiver")
    await room.connect(LIVEKIT_URL, token)
    logger.info("Connected to room %s", room.name)

    if not ser:
        logger.warning("Running without serial connection - will only log received gamepad data")
    else:
        logger.info("Ready to forward gamepad controls to serial port")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        handlers=[
            logging.FileHandler("rover.log"),
            logging.StreamHandler(),
        ],
    )

    loop = asyncio.get_event_loop()
    room = rtc.Room(loop=loop)

    async def cleanup():
        await room.disconnect()
        loop.stop()

    asyncio.ensure_future(main(room))
    for signal in [SIGINT, SIGTERM]:
        loop.add_signal_handler(signal, lambda: asyncio.ensure_future(cleanup()))

    try:
        loop.run_forever()
    finally:
        loop.close()

