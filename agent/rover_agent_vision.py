
#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
#   "livekit-agents[deepgram,openai,cartesia,silero,elevenlabs,turn-detector,hume]~=1.0",
#   "livekit-plugins-noise-cancellation~=0.2",
#   "python-dotenv",
# ]
# ///

import asyncio
import json
import logging
from dotenv import load_dotenv

from livekit import agents, rtc
from livekit.agents.llm import function_tool, ImageContent, ChatContext, ChatMessage
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
logger.setLevel(logging.INFO)


class Assistant(Agent):
    def __init__(self) -> None:
        self._video_stream = None
        self._latest_frame = None
        self._tasks = []
        
        
        super().__init__(instructions="""
                         You are a robot rover controlled by a user via voice commands.
        #                  You do not need to respond to the user, you will only do what the user asks you to do.
        #                  The user may also publish a video stream to you, you will use this to see what the user is seeing.
                         
        #                  You have access to the following functions:
        #                  - move_forward(distance: float, velocity: float, steering: float = 0.0)
        #                  - move_backward(distance: float, velocity: float, steering: float = 0.0)
                         
                         the user can give you commands like the following, which you can call the functions to move the rover:
        #                  Move backwards 3 meters
        #                  Move forward 5 meters at 1 meter per second
        #                  Move forward 2 meters at 0.5 meters per second with a sharp right turn
        #                  Move forwards 1 meter while making a sharp left turn
        #                  Move forwards 1 meter with a left turn
        #                  Move forwards 1 meters with steering of 0.8
        #                  Drive forward 1 meter
        #                  Drive backwards 2 meters
                           Drive towards the blue object
                           Drive towards teh red object
                           Move towards the green toy
                         
                          #end of examples
                         
                         If the user asks you to move towards an object, you will call the function move_forward with distance=0.3, velocity=0.5 and for the steering value
                         you will generate a value based on where the object is in the image.  If the object is in the the left side of the image, you will use a negative number between -0.3 and -0.6.  
                         If the object is in the the right side of the image, you will use a positive number between 0.3 and 0.6.
                         If the object is in the center of the image, you will use a value of 0.0.
                         
                          If the user gives you a command that is not one of the above, you will do nothing and say nothing in response.
                         When responding to a valid command, just say "OK" and do not say anything else.
                         
                         """)
        
        # super().__init__(instructions="""
        #                  You are a robot rover controlled by a user via voice commands.
        #                  You do not need to respond to the user, you will only do what the user asks you to do.
        #                  The user may also publish a video stream to you, you will use this to see what the user is seeing.
                         
        #                  You have access to the following functions:
        #                  - move_forward(distance: float, velocity: float, steering: float = 0.0)
        #                  - move_backward(distance: float, velocity: float, steering: float = 0.0)
                         
        #                  the user can give you commands like the following, which you can call the functions to move the rover:
        #                  Move backwards 3 meters
        #                  Move forward 5 meters at 1 meter per second
        #                  Move forward 2 meters at 0.5 meters per second with a sharp right turn
        #                  Move forwards 1 meter while making a sharp left turn
        #                  Move forwards 1 meter with a left turn
        #                  Move forwards 1 meters with steering of 0.8
        #                  Drive forward 1 meter
        #                  Drive backwards 2 meters
                         
                         
        #                 the user can also give you commands to take an action based on the video stream, such as:
        #                 Move towards the red ball
        #                 Drive forward between the furniture
                         
        #                 #end of examples
                         
        #                 When the user give you a command to take an action based on the video stream, if the objects in reference can be seen, generate actions
        #                  function calls to navigate the rover to the object, 1 meter at a time, with appropriate steering and velocity. 
                         
        #                 Rules to follow:
        #                  If velocity is not provided, default to 1 meter per second.
        #                  If steering is not provided, default to 0.0 (straight).
        #                  If distance is not provided, default to 1 meter.
        #                  If turn or steering is desired, the value should be between -1.0 - -0.4 for left turn and 0.4 - 1.0 for right turn.
        #                  If turn or steering is given using a word such as "sharp left turn" or "slight right turn" or "moderate right turn", map that to a value between -1.0 - -0.4 or 0.4 - 1.0 depending on the direction.
                         
        #                  If the user gives you a command that is not one of the above, you will do nothing and say nothing in response.
                         
        #                  """)

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
    
    async def on_enter(self):
        room = get_job_context().room

        # Find the first video track (if any) from the remote participant
        if room.remote_participants:
            
            for remote_participant in room.remote_participants.values():
                video_tracks = [
                    publication.track
                    for publication in list(remote_participant.track_publications.values())
                    if publication.track and publication.track.kind == rtc.TrackKind.KIND_VIDEO
                ]
                if video_tracks:
                    logger.info(f"particiant: {remote_participant.identity} video_tracks: {video_tracks[0]}")
                    if (remote_participant.identity == 'rover-cam'):
                        logger.info(f"Creating video stream for rover-cam")
                        self._create_video_stream(video_tracks[0])
                    
                # audio_tracks = [
                #     publication.track
                #     for publication in list(remote_participant.track_publications.values())
                #     if publication.track and publication.track.kind == rtc.TrackKind.KIND_AUDIO
                # ]
                # if audio_tracks:
                #     logger.info(f"particiant: {remote_participant.identity} audio_tracks: {audio_tracks[0]}")
                    # self._create_audio_stream(audio_tracks[0])
                    

        # Watch for new video tracks not yet published
        @room.on("track_subscribed")
        def on_track_subscribed(track: rtc.Track, publication: rtc.RemoteTrackPublication, participant: rtc.RemoteParticipant):
            if track.kind == rtc.TrackKind.KIND_VIDEO:
                self._create_video_stream(track)
                
        @room.on("participant_joined")
        def on_participant_joined(participant: rtc.RemoteParticipant):
            logger.info(f"Participant joined: {participant.identity}")
            
    
    async def on_user_turn_completed(self, turn_ctx: ChatContext, new_message: ChatMessage) -> None:
        # Add the latest video frame, if any, to the new message
        logger.info(f"on_user_turn_completed {self._latest_frame}")
        if self._latest_frame:
            new_message.content.append(ImageContent(image=self._latest_frame))
            self._latest_frame = None
                  
    def _create_video_stream(self, track: rtc.Track):
        # Close any existing stream (we only want one at a time)
        if self._video_stream is not None:
            logger.info(f"Video stream already exists")
            return #self._video_stream.aclose()

        # Create a new stream to receive frames
        logger.info(f"Creating video stream")
        self._video_stream = rtc.VideoStream(track)
        async def read_stream():
            async for event in self._video_stream:
                # Store the latest frame for use later
                self._latest_frame = event.frame

        # Store the async task
        task = asyncio.create_task(read_stream())
        task.add_done_callback(lambda t: self._tasks.remove(t))
        self._tasks.append(task)

async def entrypoint(ctx: agents.JobContext):
    await ctx.connect(
        # auto_subscribe=agents.AutoSubscribe.SUBSCRIBE_NONE
    )

    session = AgentSession(
        stt=deepgram.STT(model="nova-3", language="en"),
        # llm=openai.LLM(model="gpt-4o"),
        llm=openai.LLM.with_x_ai(model="grok-2-vision"),
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
            participant_identity='rover'
            # LiveKit Cloud enhanced noise cancellation
            # - If self-hosting, omit this parameter
            # - For telephony applications, use `BVCTelephony` for best results
            #noise_cancellation=noise_cancellation.BVC(), 
        ),
    )


if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint, agent_name="rover_agent"))