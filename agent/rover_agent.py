
#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
#   "livekit-agents[deepgram,openai,cartesia,silero,elevenlabs,turn-detector,hume]~=1.0",
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
    elevenlabs,
    deepgram,
    noise_cancellation,
    silero,
)

load_dotenv()

logger = logging.getLogger("rover-agent")


class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(instructions="""
                         You are a robot rover controlled by a user via voice commands.
                         You do not need to respond to the user, you will only do what the user asks you to do.
                         
                         You have access to the following functions:
                         - move_forward(distance: float, velocity: float, steering: float = 0.0)
                         - move_backward(distance: float, velocity: float, steering: float = 0.0)
                         
                         the user can give you commands like this:
                         
                         Move backwards 3 meters
                         Move forward 5 meters at 1 meter per second
                         Move forward 2 meters at 0.5 meters per second with a sharp right turn
                         Move forwards 1 meters with steering of 0.8
                         Drive forward 1 meter
                         Drive backwards 2 meters
                         
                         
                         If velocity is not provided, default to 1 meter per second.
                         If steering is not provided, default to 0.0 (straight).
                         If distance is not provided, default to 1 meter.
                         If turn or steering is desired, the value should be between -1.0 - -0.4 for left turn and 0.4 - 1.0 for right turn.
                         If turn or steering is given using a word such as "sharp left turn" or "slight right turn" or "moderate right turn", map that to a value between -1.0 - -0.4 or 0.4 - 1.0 depending on the direction.
                         
                         If the user gives you a command that is not one of the above, you will do nothing and say nothing in response.
                         
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
        llm=openai.LLM(model="gpt-4o"),
        tts=elevenlabs.TTS(
                model="eleven_multilingual_v2"
            ),
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
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint, agent_name="rover_agent"))