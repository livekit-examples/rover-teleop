
#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
#   "livekit-agents[deepgram,openai,cartesia,silero,turn-detector,hume]~=1.0",
#   "livekit-plugins-noise-cancellation~=0.2",
#   "python-dotenv",
# ]
# ///

import json
import logging
from dotenv import load_dotenv

from livekit import agents
from livekit.agents import AgentSession, Agent, RoomInputOptions, get_job_context, RunContext
from livekit.agents.llm import function_tool
from livekit.plugins import (
    openai,
    cartesia,
    deepgram,
    noise_cancellation,
    silero,
    hume,
)

load_dotenv()

logger = logging.getLogger("rover-agent")


class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(instructions="""
                         You are a robot named rover.
                         You are controlled by a user via voice commands.
                         You will only respond to commands that start with "rover".
                         Here are the commands you can use:
                         - move_forward <distance in meters> <velocity m/s> <steering -1.0 to 1.0>
                         - move_backward <distance in meters> <velocity m/s> <steering -1.0 to 1.0>
                         
                         the user can give you commands like this:
                         Move backwards 3 meters
                         Move forward 5 meters at 1 meter per second
                         Move forward 2 meters at 0.5 meters per second with a sharp right turn
                         Move forward 1 meters with steering of 0.8
                         
                         
                         If velocity is not provided, it will default to 1 meter per second.
                         If steering is not provided, it will default to 0.0 (straight).
                         If distance is not provided, it will default to 1 meter.
                         
                         If the user gives you a command that is not one of the above, you will do nothing.
                         the turn value can be inferred from description such as "Sharp right turn" or "slight left turn" which can be mapped to 1.0 or -0.6.
                         """)

    @function_tool
    async def move_forward(
        self,
        context: RunContext,
        distance: float,
        velocity: float,
        steering: float = 0.0
    ):
        """Move the rover forward.
        
        Args:
            distance: Distance to move in meters (must be > 0)
            velocity: Velocity in m/s (must be > 0)
            steering: Steering value from -1.0 to 1.0 (0.0 = straight)
        """
        try:
            # Validate parameters
            if distance <= 0:
                return f"Invalid distance: {distance}. Must be greater than 0."
            
            if velocity <= 0:
                return f"Invalid velocity: {velocity}. Must be greater than 0."
            
            if not -1.0 <= steering <= 1.0:
                return f"Invalid steering: {steering}. Must be between -1.0 and 1.0."
            
            # Create command packet
            command = {
                "type": "forward",
                "distance": distance,
                "velocity": velocity,
                "steering": steering
            }
            
            # Get room and send command
            ctx = get_job_context()
            room = ctx.room
            
            command_bytes = json.dumps(command).encode('utf-8')
            await room.local_participant.publish_data(
                command_bytes,
                reliable=True,
                topic="command"
            )
            
            logger.info(f"Sent forward command: distance={distance}m, velocity={velocity}m/s, steering={steering}")
            return f"Moving forward {distance} meters at {velocity} m/s with steering {steering}"
            
        except Exception as e:
            logger.error(f"Error sending forward command: {e}")
            return f"Error sending forward command: {str(e)}"

    @function_tool
    async def move_backward(
        self,
        context: RunContext,
        distance: float,
        velocity: float,
        steering: float = 0.0
    ):
        """Move the rover backward.
        
        Args:
            distance: Distance to move in meters (must be > 0)
            velocity: Velocity in m/s (must be > 0)
            steering: Steering value from -1.0 to 1.0 (0.0 = straight)
        """
        try:
            # Validate parameters
            if distance <= 0:
                return f"Invalid distance: {distance}. Must be greater than 0."
            
            if velocity <= 0:
                return f"Invalid velocity: {velocity}. Must be greater than 0."
            
            if not -1.0 <= steering <= 1.0:
                return f"Invalid steering: {steering}. Must be between -1.0 and 1.0."
            
            # Create command packet
            command = {
                "type": "backward",
                "distance": distance,
                "velocity": velocity,
                "steering": steering
            }
            
            # Get room and send command
            ctx = get_job_context()
            room = ctx.room
            
            command_bytes = json.dumps(command).encode('utf-8')
            await room.local_participant.publish_data(
                command_bytes,
                reliable=True,
                topic="command"
            )
            
            logger.info(f"Sent backward command: distance={distance}m, velocity={velocity}m/s, steering={steering}")
            return f"Moving backward {distance} meters at {velocity} m/s with steering {steering}"
            
        except Exception as e:
            logger.error(f"Error sending backward command: {e}")
            return f"Error sending backward command: {str(e)}"


async def entrypoint(ctx: agents.JobContext):
    session = AgentSession(
        stt=deepgram.STT(model="nova-3", language="en"),
        llm=openai.LLM(model="gpt-4o-mini"),
        tts=deepgram.TTS(model="aura-asteria-en"),
        vad=silero.VAD.load(),
        # turn_detection=EnglishModel(),
    ) 

    await session.start(
        room=ctx.room,
        agent=Assistant(),
        room_input_options=RoomInputOptions(
            # LiveKit Cloud enhanced noise cancellation
            # - If self-hosting, omit this parameter
            # - For telephony applications, use `BVCTelephony` for best results
            noise_cancellation=noise_cancellation.BVC(), 
        ),
    )

    await ctx.connect()

    await session.generate_reply(
        instructions="Stand by, awaiting user command"
    )


if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))