import os
import logging
import asyncio
import json
import serial
from dotenv import load_dotenv
from signal import SIGINT, SIGTERM
from livekit import rtc
from auth import generate_token

load_dotenv("../.env")
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
            logger.info("Data received: %s", decoded_data)
            
            # Try to parse as JSON
            json_data = json.loads(decoded_data)
            
            # Check if we have the expected thumbstick values
            if all(k in json_data for k in ["left_x", "left_y", "right_x", "right_y"]):
                # Map left_y and right_y to a range of -0.5 to 0.5
                # Gamepad values are typically in range [-1, 1]
                left_y = float(json_data['left_y'])
                right_y = float(json_data['right_y'])  # Note: Using right_x as that's often the throttle
                
                # Scale to [-0.5, 0.5] range
                # No need to scale if already in [-1, 1] range, just multiply by 0.5
                left_y_scaled = -1 * round(left_y * 0.5, 3)
                right_y_scaled = -1 * round(right_y * 0.5, 3)
                
                # Create command JSON as specified
                command_data = {
                    "T": 1,  # Type 1 for motor control
                    "L": left_y_scaled,
                    "R": right_y_scaled
                }
                
                # Convert to JSON string
                command_json = json.dumps(command_data)
                logger.info(f"Formatted command: {command_json}")
                
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

