#!/usr/bin/env python3
"""
SlowPlay audio player using sounddevice + scipy
Lightweight alternative to GStreamer with real-time speed/pitch control
"""

import numpy as np
import sounddevice as sd
import soundfile as sf
import threading
import queue
import os
from scipy import signal
from datetime import datetime

from CTkMessagebox import CTkMessagebox
import gettext
_ = gettext.gettext

# Constants
NANOSEC = 1000000000
DEFAULT_BLOCK_SIZE = 4096
PRELOAD_BLOCKS = 4


class slowPlayer():
    def __init__(self):
        """Initialize the audio player"""
        
        # Audio data storage
        self._audio_data = None  # Shape: (channels, samples)
        self._sample_rate = 44100
        self._current_frame = 0  # Current position in frames
        self._total_frames = 0
        
        # Playback parameters
        self._speed = 1.0  # 1.0 = normal, 0.5 = half speed, 2.0 = double speed
        self._pitch = 1.0  # 1.0 = normal, 0.5 = octave down, 2.0 = octave up
        self._volume = 1.0
        
        # Playback state
        self.media = ""
        self.canPlay = False
        self.isPlaying = False
        self.songPosition = 0.0  # Position in seconds
        self.updateInterval = 20  # milliseconds
        self.startPoint = -2  # Loop start in nanoseconds
        self.endPoint = -1  # Loop end in nanoseconds
        self.loopEnabled = False
        
        # Metadata
        self.title = ""
        self.artist = ""
        
        # Audio output
        self._stream = None
        self._audio_queue = queue.Queue(maxsize=PRELOAD_BLOCKS)
        self._stop_thread = threading.Event()
        self._processing_thread = None
        
        # Thread safety
        self._lock = threading.Lock()
        
        # For compatibility
        self.semitones = 0
        self.cents = 0
        self.tempo = 1.0

    def _resample_block(self, block, target_ratio):
        """Resample audio block to change speed/pitch"""
        if target_ratio == 1.0:
            return block
        
        # Calculate new length
        orig_len = block.shape[-1]
        new_len = int(orig_len * target_ratio)
        
        if len(block.shape) == 1:
            # Mono
            return signal.resample(block, new_len)
        else:
            # Multi-channel
            result = np.zeros((block.shape[0], new_len), dtype=block.dtype)
            for ch in range(block.shape[0]):
                result[ch] = signal.resample(block[ch], new_len)
            return result

    def _get_audio_block(self, block_size):
        """Get next audio block with speed/pitch applied"""
        with self._lock:
            if self._audio_data is None:
                return None
            
            # Calculate how many input frames we need
            # At speed 0.5, we need half the frames for same output
            # At speed 2.0, we need double the frames
            input_frames_needed = int(block_size * self._speed)
            
            # Get current channel count
            channels = self._audio_data.shape[0]
            
            # Check for loop boundaries
            if self.loopEnabled and self.endPoint > 0:
                current_time = self._current_frame / self._sample_rate
                end_time = self.endPoint / NANOSEC
                
                if current_time >= end_time:
                    # Loop back
                    if self.startPoint >= 0:
                        start_time = self.startPoint / NANOSEC
                        self._current_frame = int(start_time * self._sample_rate)
                    else:
                        self._current_frame = 0
            
            # Calculate read range
            start_frame = self._current_frame
            end_frame = min(start_frame + input_frames_needed, self._total_frames)
            
            # Check if we've reached the end
            if start_frame >= self._total_frames:
                if self.loopEnabled:
                    # Loop back to start
                    if self.startPoint >= 0:
                        start_time = self.startPoint / NANOSEC
                        self._current_frame = int(start_time * self._sample_rate)
                    else:
                        self._current_frame = 0
                    return self._get_audio_block(block_size)
                else:
                    return None  # End of file
            
            # Extract audio slice
            audio_slice = self._audio_data[:, start_frame:end_frame]
            
            # Update position
            self._current_frame = end_frame
            
            # Apply pitch shift by resampling
            if self._pitch != 1.0:
                # Pitch shift is done by resampling
                # Higher pitch = higher sample rate = shorter audio
                pitch_ratio = 1.0 / self._pitch
                audio_slice = self._resample_block(audio_slice, pitch_ratio)
            
            # Apply speed (tempo) change
            # Speed < 1 (slower) = need more output samples
            # Speed > 1 (faster) = need fewer output samples
            speed_ratio = 1.0 / self._speed
            
            # Only resample if speed is not 1.0 and we need specific output size
            if self._speed != 1.0:
                audio_slice = self._resample_block(audio_slice, speed_ratio)
            
            # Ensure we have exactly block_size samples
            current_len = audio_slice.shape[1] if len(audio_slice.shape) > 1 else len(audio_slice)
            
            if current_len < block_size:
                # Pad with zeros
                padding = block_size - current_len
                if len(audio_slice.shape) == 1:
                    audio_slice = np.pad(audio_slice, (0, padding), mode='constant')
                else:
                    audio_slice = np.pad(audio_slice, ((0, 0), (0, padding)), mode='constant')
            elif current_len > block_size:
                # Truncate
                audio_slice = audio_slice[:, :block_size] if len(audio_slice.shape) > 1 else audio_slice[:block_size]
            
            # Apply volume
            audio_slice = audio_slice * self._volume
            
            return audio_slice.astype(np.float32)

    def _audio_callback(self, outdata, frames, time_info, status):
        """SoundDevice callback"""
        if status:
            if status.output_underflow:
                print("Audio output underflow")
        
        try:
            data = self._audio_queue.get_nowait()
            if data is None:
                # End of playback
                outdata.fill(0)
                self.isPlaying = False
                return
            
            # Ensure correct shape
            if len(data.shape) == 1:
                # Mono - copy to all output channels
                if outdata.shape[1] == 1:
                    outdata[:, 0] = data[:frames]
                else:
                    for ch in range(outdata.shape[1]):
                        outdata[:, ch] = data[:frames]
            else:
                # Multi-channel
                num_channels = min(data.shape[0], outdata.shape[1])
                for ch in range(num_channels):
                    outdata[:, ch] = data[ch, :frames]
                
                # Fill remaining channels if any
                for ch in range(num_channels, outdata.shape[1]):
                    outdata[:, ch] = outdata[:, 0]
                    
        except queue.Empty:
            # Buffer underrun - fill with silence
            outdata.fill(0)

    def _processing_thread_func(self):
        """Background thread to pre-process audio"""
        block_size = DEFAULT_BLOCK_SIZE
        
        while not self._stop_thread.is_set():
            if self.isPlaying:
                # Check if queue has space
                if not self._audio_queue.full():
                    block = self._get_audio_block(block_size)
                    try:
                        self._audio_queue.put(block, timeout=0.1)
                        if block is None:
                            # End of file
                            break
                    except queue.Full:
                        pass
                else:
                    # Queue is full, wait a bit
                    self._stop_thread.wait(0.01)
            else:
                self._stop_thread.wait(0.01)

    def MediaLoad(self, mediafile):
        """Load audio file"""
        # Stop current playback
        self.Pause()
        
        # Convert URI to path
        if mediafile.startswith("file://"):
            mediafile = mediafile[7:]
            # On Windows, remove leading '/' from paths like '/C:/...'
            if mediafile.startswith("/") and len(mediafile) > 2 and mediafile[2] == ":":
                mediafile = mediafile[1:]
        
        try:
            # Load audio file
            data, samplerate = sf.read(mediafile, dtype=np.float32)
            
            # Handle shape: ensure (channels, samples)
            if len(data.shape) == 1:
                # Mono - add channel dimension
                self._audio_data = data.reshape(1, -1)
            else:
                # Stereo or more - transpose to (channels, samples)
                self._audio_data = data.T
            
            self._sample_rate = samplerate
            self._total_frames = self._audio_data.shape[1]
            self._current_frame = 0
            
            self.media = mediafile
            self.canPlay = True
            self.title = os.path.splitext(os.path.basename(mediafile))[0]
            self.artist = ""
            
            # Extract metadata if available
            try:
                info = sf.info(mediafile)
                # Try to get title/artist from comments if available
            except:
                pass
                
        except Exception as e:
            print(f"Error loading file: {e}")
            self.canPlay = False
            self._audio_data = None

    def _init_stream(self):
        """Initialize audio output stream"""
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except:
                pass
        
        if self._audio_data is None:
            return
        
        channels = self._audio_data.shape[0]
        
        try:
            self._stream = sd.OutputStream(
                samplerate=self._sample_rate,
                channels=channels,
                dtype=np.float32,
                blocksize=DEFAULT_BLOCK_SIZE,
                callback=self._audio_callback
            )
        except Exception as e:
            print(f"Error creating audio stream: {e}")
            # Try with default device
            sd.default.reset()
            self._stream = sd.OutputStream(
                samplerate=self._sample_rate,
                channels=channels,
                dtype=np.float32,
                blocksize=DEFAULT_BLOCK_SIZE,
                callback=self._audio_callback
            )

    def Play(self):
        """Start playback"""
        if not self.canPlay or self._audio_data is None:
            return
        
        if not self.isPlaying:
            self.isPlaying = True
            
            # Initialize stream if needed
            if self._stream is None:
                self._init_stream()
            
            # Clear and pre-fill queue
            while not self._audio_queue.empty():
                try:
                    self._audio_queue.get_nowait()
                except queue.Empty:
                    break
            
            # Pre-fill buffer
            for _ in range(PRELOAD_BLOCKS):
                block = self._get_audio_block(DEFAULT_BLOCK_SIZE)
                if block is not None:
                    try:
                        self._audio_queue.put(block, block=False)
                    except queue.Full:
                        break
                else:
                    break
            
            # Start stream
            self._stream.start()
            
            # Start processing thread
            self._stop_thread.clear()
            self._processing_thread = threading.Thread(target=self._processing_thread_func, daemon=True)
            self._processing_thread.start()

    def Pause(self):
        """Pause playback"""
        self.isPlaying = False
        
        if self._stream is not None:
            try:
                self._stream.stop()
            except:
                pass
        
        self._stop_thread.set()
        
        if self._processing_thread is not None:
            self._processing_thread.join(timeout=0.5)
            self._processing_thread = None

    def Rewind(self):
        """Rewind to start or loop point"""
        with self._lock:
            if self.loopEnabled and self.startPoint >= 0:
                start_time = self.startPoint / NANOSEC
                self._current_frame = int(start_time * self._sample_rate)
            else:
                self._current_frame = 0
            
            # Clamp to valid range
            self._current_frame = max(0, min(self._current_frame, self._total_frames - 1))

    def seek_absolute(self, newPos):
        """Seek to absolute position (newPos in nanoseconds)"""
        with self._lock:
            new_time = newPos / NANOSEC
            self._current_frame = int(new_time * self._sample_rate)
            self._current_frame = max(0, min(self._current_frame, self._total_frames - 1))
            self.songPosition = new_time

    def seek_relative(self, newPos):
        """Seek relative to current position (newPos in seconds)"""
        current_time = self._current_frame / self._sample_rate
        new_time = current_time + newPos
        self.seek_absolute(new_time * NANOSEC)

    def query_position(self):
        """Get current position in nanoseconds"""
        if self._audio_data is None:
            return None
        pos_sec = self._current_frame / self._sample_rate
        return int(pos_sec * NANOSEC)

    def query_duration(self):
        """Get duration in nanoseconds"""
        if self._audio_data is None:
            return None
        duration_sec = self._total_frames / self._sample_rate
        return int(duration_sec * NANOSEC)

    def query_percentage(self):
        """Get position as percentage (0-1000000)"""
        if self._audio_data is None or self._total_frames == 0:
            return None
        return int(self._current_frame / self._total_frames * 1000000)

    def update_position(self):
        """Update and return position"""
        return (self.query_duration(), self.query_position())

    def handle_message(self):
        """Handle messages (compatibility)"""
        pass

    def ReadyToPlay(self):
        """Prepare for playback"""
        self.canPlay = True

    def get_speed(self):
        """Get current tempo"""
        return self._speed

    def set_speed(self, speed):
        """Set playback tempo"""
        with self._lock:
            self._speed = max(0.25, min(4.0, speed))
            self.tempo = self._speed

    def set_pitch(self, semitones):
        """Set pitch shift in semitones"""
        with self._lock:
            # Convert semitones to ratio
            # 12 semitones = 1 octave = 2x frequency
            self._pitch = 2 ** (semitones / 12.0)

    def set_volume(self, volume):
        """Set volume (0.0 to 1.0)"""
        self._volume = max(0.0, min(1.0, volume))

    def pipeline_time(self, t):
        """Convert song time to pipeline time"""
        if t is None:
            return None
        return int(t / self._speed * NANOSEC)

    def song_time(self, t):
        """Convert pipeline time to song time"""
        if t is None:
            return None
        return t * self._speed / NANOSEC

    def fileSave(self, src, dest, callback=None):
        """Export audio file with current tempo/pitch settings using rubberband CLI"""
        try:
            # For export, we use rubberband CLI if available, otherwise scipy
            import subprocess
            import shutil
            
            has_rubberband = shutil.which("rubberband") is not None or shutil.which("rubberband.exe") is not None
            
            if has_rubberband and self._speed != 1.0 or self._pitch != 1.0:
                # Use rubberband for high quality export
                tempo_opt = f"--tempo {self._speed * 100:.1f}"
                pitch_opt = f"--pitch {12 * np.log2(self._pitch):.1f}" if self._pitch != 1.0 else ""
                
                cmd = ["rubberband", tempo_opt] + ([pitch_opt] if pitch_opt else []) + [src, dest]
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode != 0:
                    raise RuntimeError(f"rubberband failed: {result.stderr}")
            else:
                # Use scipy for export (fallback)
                data, sr = sf.read(src, dtype=np.float32)
                
                # Apply speed change
                if self._speed != 1.0:
                    orig_len = len(data)
                    new_len = int(orig_len / self._speed)
                    if len(data.shape) == 1:
                        data = signal.resample(data, new_len)
                    else:
                        data = signal.resample(data, new_len, axis=0)
                
                # Apply pitch change
                if self._pitch != 1.0:
                    pitch_ratio = 1.0 / self._pitch
                    if len(data.shape) == 1:
                        data = signal.resample(data, int(len(data) * pitch_ratio))
                    else:
                        data = signal.resample(data, int(data.shape[0] * pitch_ratio), axis=0)
                
                sf.write(dest, data, sr)
            
            if callback:
                callback(100)
                
        except Exception as e:
            print(f"Error saving file: {e}")
            raise

    def __del__(self):
        """Cleanup"""
        self.Pause()
        if self._stream is not None:
            try:
                self._stream.close()
            except:
                pass
