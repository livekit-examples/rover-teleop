import asyncio
import logging
import time
import sounddevice as sd
import numpy as np
from livekit import rtc

# Audio constants
SAMPLE_RATE = 48000  # 48kHz to match DC Microphone native rate
NUM_CHANNELS = 1
FRAME_SAMPLES = 480  # 10ms at 48kHz
BLOCKSIZE = 2400  # 50ms buffer - reduced to prevent overflow

class AudioManager:
    def __init__(self, loop: asyncio.AbstractEventLoop):
        self.loop = loop
        self.running = True
        self.logger = logging.getLogger(__name__)
        
        # Audio components
        self.input_stream: sd.InputStream | None = None
        self.source = rtc.AudioSource(SAMPLE_RATE, NUM_CHANNELS)
        # Increase queue size significantly to handle bursts
        # With 50ms blocks, 500 items = 25 seconds of audio buffer
        self.audio_input_queue = asyncio.Queue(maxsize=500)
        
        # Debug counters
        self.input_callback_count = 0
        self.frames_processed = 0
        self.frames_sent_to_livekit = 0
        self.queue_full_count = 0
        self.overflow_count = 0
        self.processing_errors = 0
        
        # Performance monitoring
        self.last_stats_time = time.time()
        self.stats_interval = 10.0  # Log stats every 10 seconds
        
    def start_audio_devices(self):
        """Initialize and start audio input device"""
        try:
            self.logger.info("Starting audio input device...")
            
            # List all devices for debugging
            self.logger.info("Available audio devices:")
            try:
                devices = sd.query_devices()
                for i, device in enumerate(devices):
                    self.logger.info(f"  {i}: {device['name']} - {device['max_input_channels']} input channels")
            except Exception as e:
                self.logger.warning(f"Could not list audio devices: {e}")
            
            # Get default input device
            input_device, _ = sd.default.device
            self.logger.info(f"Using input device: {input_device}")
            
            if input_device is not None:
                device_info = sd.query_devices(input_device)
                if isinstance(device_info, dict):
                    self.logger.info(f"Input device info: {device_info}")
                    
                    # Check if device supports our requirements
                    if device_info['max_input_channels'] < NUM_CHANNELS:
                        self.logger.warning(f"Input device only has {device_info['max_input_channels']} channels, need {NUM_CHANNELS}")
            
            # Start input stream with optimized settings
            self.input_stream = sd.InputStream(
                callback=self._input_callback,
                dtype="int16",
                channels=NUM_CHANNELS,
                device=input_device,
                samplerate=SAMPLE_RATE,
                blocksize=BLOCKSIZE,  # Use reduced buffer size to prevent overflow
                latency='low',  # Request low latency mode
            )
            self.input_stream.start()
            self.logger.info("Started audio input stream")
            
            # Test if stream is active
            time.sleep(0.1)  # Give stream time to start
            self.logger.info(f"Input stream active: {self.input_stream.active}")
            
        except Exception as e:
            self.logger.error(f"Failed to start audio devices: {e}")
            raise
    
    def stop_audio_devices(self):
        """Stop and cleanup audio devices"""
        self.logger.info("Stopping audio devices...")
        self.running = False
        
        if self.input_stream:
            self.input_stream.stop()
            self.input_stream.close()
            self.input_stream = None
            self.logger.info("Stopped input stream")
        
        # Log final statistics
        self._log_stats(final=True)
    
    def _input_callback(self, indata: np.ndarray, frame_count: int, time_info, status) -> None:
        """Sounddevice input callback - optimized for minimal processing"""
        self.input_callback_count += 1
        
        if status:
            if status.input_overflow:
                self.overflow_count += 1
                if self.overflow_count <= 10 or self.overflow_count % 50 == 0:
                    self.logger.warning(f"Input overflow #{self.overflow_count}")
            else:
                self.logger.warning(f"Input callback status: {status}")
            
        if not self.running:
            return
            
        # Log first few callbacks for debugging
        if self.input_callback_count <= 3:
            self.logger.info(f"Input callback #{self.input_callback_count}: "
                           f"frame_count={frame_count}, "
                           f"indata.shape={indata.shape}, "
                           f"indata.dtype={indata.dtype}")
        
        try:
            # Just copy the raw audio data - minimal processing in callback
            if self.loop and not self.loop.is_closed():
                try:
                    # Copy the audio data to avoid numpy array ownership issues
                    # Use a more efficient copy for the callback
                    audio_data = indata.copy() if indata.flags.c_contiguous else np.ascontiguousarray(indata)
                    
                    # Queue the raw audio data for processing
                    self.loop.call_soon_threadsafe(
                        self._try_queue_audio_data, audio_data
                    )
                    
                except Exception as e:
                    if self.frames_processed <= 10:
                        self.logger.warning(f"Failed to queue audio data: {e}")
                        
        except Exception as e:
            self.logger.error(f"Error in audio input callback: {e}")
    
    def _try_queue_audio_data(self, audio_data: np.ndarray) -> None:
        """Try to queue audio data, handling queue full gracefully"""
        try:
            self.audio_input_queue.put_nowait(audio_data)
            self.frames_sent_to_livekit += 1
            
            if self.frames_sent_to_livekit <= 3:
                self.logger.info(f"Queued audio data {self.frames_sent_to_livekit}")
                
        except asyncio.QueueFull:
            self.queue_full_count += 1
            # More aggressive queue management - drop oldest data when full
            try:
                # Try to remove oldest item and add new one
                self.audio_input_queue.get_nowait()
                self.audio_input_queue.put_nowait(audio_data)
                if self.queue_full_count % 50 == 1:
                    self.logger.warning(f"Audio queue full ({self.queue_full_count} times) - dropping oldest data")
            except asyncio.QueueEmpty:
                # Queue became empty, try to add new data
                try:
                    self.audio_input_queue.put_nowait(audio_data)
                except asyncio.QueueFull:
                    if self.queue_full_count % 50 == 1:
                        self.logger.warning(f"Audio queue still full - dropping frame")
    
    def _log_stats(self, final=False):
        """Log performance statistics"""
        current_time = time.time()
        if final or (current_time - self.last_stats_time) >= self.stats_interval:
            self.logger.info(f"Audio stats: "
                           f"callbacks={self.input_callback_count}, "
                           f"processed={self.frames_processed}, "
                           f"sent_to_livekit={self.frames_sent_to_livekit}, "
                           f"queue_full={self.queue_full_count}, "
                           f"overflows={self.overflow_count}, "
                           f"errors={self.processing_errors}")
            self.last_stats_time = current_time
    
    async def audio_processing_task(self):
        """Process audio frames from input queue and send to LiveKit - optimized version"""
        frames_sent = 0
        self.logger.info("Audio processing task started")
        
        # Pre-allocate buffer for efficiency
        frame_buffer = np.empty(FRAME_SAMPLES, dtype=np.int16)
        
        while self.running:
            try:
                # Get audio data from input callback with shorter timeout
                audio_data = await asyncio.wait_for(self.audio_input_queue.get(), timeout=0.5)
                
                # Process audio in 10ms frames more efficiently
                # Each block is 50ms, so we get 5 frames per block
                frame_count = audio_data.shape[0]
                num_frames = frame_count // FRAME_SAMPLES
                
                for i in range(num_frames):
                    start = i * FRAME_SAMPLES
                    end = start + FRAME_SAMPLES
                    if end > frame_count:
                        break
                    
                    # Extract single channel data efficiently
                    if audio_data.ndim == 2:
                        frame_buffer[:] = audio_data[start:end, 0]
                    else:
                        frame_buffer[:] = audio_data[start:end]
                    
                    # Create audio frame
                    capture_frame = rtc.AudioFrame(
                        data=frame_buffer.tobytes(),
                        samples_per_channel=FRAME_SAMPLES,
                        sample_rate=SAMPLE_RATE,
                        num_channels=NUM_CHANNELS,
                    )
                    
                    # Send to LiveKit with error handling
                    try:
                        await self.source.capture_frame(capture_frame)
                        self.frames_processed += 1
                        frames_sent += 1
                    except Exception as e:
                        self.processing_errors += 1
                        if self.processing_errors <= 5:
                            self.logger.error(f"Error sending frame to LiveKit: {e}")
                        elif self.processing_errors % 100 == 0:
                            self.logger.error(f"LiveKit errors: {self.processing_errors}")
                        # Don't break on individual frame errors
                        continue
                
                # Log stats periodically
                self._log_stats()
                        
            except asyncio.TimeoutError:
                # No frames to process, continue and log stats
                self._log_stats()
                continue
            except asyncio.CancelledError:
                # Task was cancelled, exit gracefully
                self.logger.info("Audio processing task cancelled")
                break
            except Exception as e:
                self.processing_errors += 1
                self.logger.error(f"Error in audio processing: {e}")
                # Don't break on error, try to continue
                await asyncio.sleep(0.1)
                continue
        
        self.logger.info(f"Audio processing task ended. Total frames sent: {frames_sent}")
        self._log_stats(final=True) 