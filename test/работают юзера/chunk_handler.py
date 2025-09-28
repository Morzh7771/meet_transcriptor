import os
import time
import numpy as np
import subprocess
import tempfile
from src.backend.utils.logger import CustomLog

class ChunkHandler():
    def __init__(self, chunk_duration=10):
        super().__init__()
        self.sample_rate = 16000  # Default, will be updated from client
        self.channels = 1
        self.chunk_duration = chunk_duration
        self.chunk_samples = self.sample_rate * self.chunk_duration
        self.pcm_buffer = np.array([], dtype=np.float32)
        self.t0 = time.time()
        self.paths = None
        self.chunk_count = 0
        self.logger = CustomLog()
        self.audio_config = None

    def set_paths(self, paths):
        self.paths = paths

    def set_audio_config(self, config):
        """Set audio configuration from client"""
        self.audio_config = config
        if 'sample_rate' in config:
            self.sample_rate = config['sample_rate']
            self.chunk_samples = self.sample_rate * self.chunk_duration
            self.logger.info(f"Updated audio config: {config}")

    def add_data(self, pcm_bytes):
        """Add incoming PCM float32 data to buffer with detailed diagnostics"""
        try:
            self.logger.info(f"Raw PCM data received: size={len(pcm_bytes)} bytes")
            
            # Базовые проверки
            if len(pcm_bytes) == 0:
                self.logger.warning("WARNING: Received empty PCM data!")
                return
                
            if len(pcm_bytes) % 4 != 0:
                self.logger.warning(f"WARNING: PCM data size not multiple of 4: {len(pcm_bytes)} bytes")
            
            # Показать первые байты для диагностики
            self.logger.info(f"First 20 bytes: {list(pcm_bytes[:20])}")
            
            # Попробуем разные интерпретации данных
            try:
                # Проверим как float32
                pcm_array_f32 = np.frombuffer(pcm_bytes, dtype=np.float32)
                self.logger.info(f"Float32 interpretation: length={len(pcm_array_f32)}, min={pcm_array_f32.min():.6f}, max={pcm_array_f32.max():.6f}, mean={pcm_array_f32.mean():.6f}")
                
                # Проверим, не все ли значения нули
                if np.all(pcm_array_f32 == 0):
                    self.logger.error("CRITICAL: All PCM values are ZERO! Audio data is silent!")
                
                # Проверим диапазон значений
                max_amplitude = np.max(np.abs(pcm_array_f32))
                if max_amplitude < 0.001:
                    self.logger.warning(f"WARNING: PCM values very small, max amplitude: {max_amplitude}")
                elif max_amplitude > 1.0:
                    self.logger.warning(f"WARNING: PCM values very large, max amplitude: {max_amplitude}")
                else:
                    self.logger.info(f"PCM amplitude looks good: {max_amplitude}")
                    
            except Exception as e:
                self.logger.error(f"Float32 interpretation failed: {e}")
            
            try:
                # Проверим как int16 (возможно фронт отправляет в этом формате)
                pcm_array_i16 = np.frombuffer(pcm_bytes, dtype=np.int16)
                self.logger.info(f"Int16 interpretation: length={len(pcm_array_i16)}, min={pcm_array_i16.min()}, max={pcm_array_i16.max()}")
                
                # Если float32 дает нули, но int16 дает данные - возможно проблема в формате
                if np.all(np.frombuffer(pcm_bytes, dtype=np.float32) == 0) and not np.all(pcm_array_i16 == 0):
                    self.logger.error("CRITICAL: Data looks like int16 but we're treating it as float32!")
                    
            except Exception as e:
                self.logger.error(f"Int16 interpretation failed: {e}")
            
            # Основная логика - используем float32 как было
            pcm_array = np.frombuffer(pcm_bytes, dtype=np.float32)
            self.pcm_buffer = np.concatenate([self.pcm_buffer, pcm_array])
            
            # Статистика буфера
            buffer_seconds = len(self.pcm_buffer) / self.sample_rate
            buffer_max_amplitude = np.max(np.abs(self.pcm_buffer)) if len(self.pcm_buffer) > 0 else 0
            
            # Log buffer status every 0.25 seconds worth of data
            if len(self.pcm_buffer) % (self.sample_rate // 4) == 0:
                self.logger.info(f"PCM buffer status: {buffer_seconds:.1f}s / {self.chunk_duration}s, samples: {len(self.pcm_buffer)}, max_amplitude: {buffer_max_amplitude:.6f}")
                
        except Exception as e:
            self.logger.error(f"Error adding PCM data: {e}")

    def should_finalize(self):
        """Check if we have enough samples for a chunk (10 seconds worth)"""
        should_fin = len(self.pcm_buffer) >= self.chunk_samples
        if should_fin:
            self.logger.info(f"Should finalize: {len(self.pcm_buffer)} >= {self.chunk_samples}")
        return should_fin

    def finalize(self):
        """Create webm file from accumulated PCM data with detailed diagnostics"""
        self.logger.info(f"Starting finalization. Buffer size: {len(self.pcm_buffer)}, required: {self.chunk_samples}")
        
        if len(self.pcm_buffer) < self.chunk_samples:
            self.logger.warning(f"Not enough PCM data for finalization: {len(self.pcm_buffer)} < {self.chunk_samples}")
            return None, None, None
            
        # Take exactly chunk_samples worth of data
        chunk_data = self.pcm_buffer[:self.chunk_samples]
        self.pcm_buffer = self.pcm_buffer[self.chunk_samples:]  # Keep remainder
        
        self.logger.info(f"Extracted chunk data: {len(chunk_data)} samples, remaining in buffer: {len(self.pcm_buffer)}")
        
        # Анализ данных перед конверсией
        chunk_stats = {
            "min": chunk_data.min(),
            "max": chunk_data.max(),
            "mean": chunk_data.mean(),
            "std": chunk_data.std(),
            "max_amplitude": np.max(np.abs(chunk_data)),
            "zero_count": np.sum(chunk_data == 0),
            "total_samples": len(chunk_data)
        }
        
        self.logger.info(f"Chunk statistics: {chunk_stats}")
        
        if chunk_stats["zero_count"] == chunk_stats["total_samples"]:
            self.logger.error("CRITICAL: All samples in chunk are zero!")
        elif chunk_stats["zero_count"] > chunk_stats["total_samples"] * 0.9:
            self.logger.warning(f"WARNING: {chunk_stats['zero_count']}/{chunk_stats['total_samples']} samples are zero")
        
        # Generate timestamp and paths
        timestamp = time.strftime('%Y-%m-%d_%H-%M-%S')
        webm_filename = f"chunk_{timestamp}_{self.chunk_count}.webm"
        webm_path = os.path.join(self.paths["audio"], webm_filename)
        
        # Convert PCM to webm using FFmpeg
        success = self._pcm_to_webm(chunk_data, webm_path)
        
        if success:
            self.chunk_count += 1
            chunk_start_time = int(self.t0 * 1000)  # milliseconds
            self.t0 = time.time()  # Reset timer for next chunk
            
            file_size = os.path.getsize(webm_path) if os.path.exists(webm_path) else 0
            self.logger.info(f"SUCCESS: Saved PCM chunk as webm: {webm_path}, size: {file_size} bytes")
            
            if file_size < 1000:
                self.logger.error(f"CRITICAL: Generated webm file is very small: {file_size} bytes")
            
            return webm_path, timestamp, chunk_start_time
        else:
            self.logger.error("FAILED: Could not convert PCM to webm")
            return None, None, None

    def _pcm_to_webm(self, pcm_data, output_path):
        """Convert PCM float32 data to webm using FFmpeg with detailed diagnostics"""
        try:
            self.logger.info(f"Converting PCM to webm: {len(pcm_data)} samples")
            self.logger.info(f"PCM data stats: min={pcm_data.min():.6f}, max={pcm_data.max():.6f}, mean={pcm_data.mean():.6f}")
            
            # Проверим, не пустые ли данные
            if len(pcm_data) == 0:
                self.logger.error("ERROR: PCM data is empty!")
                return False
                
            if np.all(pcm_data == 0):
                self.logger.error("ERROR: All PCM samples are zero!")
                return False
                
            # Проверим амплитуду
            max_amplitude = np.max(np.abs(pcm_data))
            if max_amplitude < 0.001:
                self.logger.warning(f"WARNING: Very low amplitude: {max_amplitude}")
            elif max_amplitude > 1.0:
                self.logger.warning(f"WARNING: Very high amplitude: {max_amplitude}, clipping may occur")
            
            # Create temporary raw PCM file
            with tempfile.NamedTemporaryFile(suffix='.raw', delete=False) as temp_file:
                # Convert float32 to int16 for FFmpeg
                # Clamp values to [-1, 1] range before conversion
                pcm_clamped = np.clip(pcm_data, -1.0, 1.0)
                int16_data = (pcm_clamped * 32767).astype(np.int16)
                
                # Дополнительная проверка после конверсии
                self.logger.info(f"Int16 conversion: min={int16_data.min()}, max={int16_data.max()}, non_zero_count={np.sum(int16_data != 0)}")
                
                if np.all(int16_data == 0):
                    self.logger.error("ERROR: All int16 samples are zero after conversion!")
                    return False
                
                int16_data.tofile(temp_file.name)
                temp_raw_path = temp_file.name
                
                # Проверим размер временного файла
                temp_size = os.path.getsize(temp_raw_path)
                expected_size = len(int16_data) * 2  # 2 bytes per int16 sample
                self.logger.info(f"Temp raw file: {temp_raw_path}, size: {temp_size} bytes, expected: {expected_size} bytes")
                
                if temp_size != expected_size:
                    self.logger.error(f"ERROR: Temp file size mismatch! Expected {expected_size}, got {temp_size}")

            # FFmpeg command
            cmd = [
                'ffmpeg',
                '-f', 's16le',  # Input format: signed 16-bit little endian
                '-ar', str(self.sample_rate),  # Sample rate
                '-ac', str(self.channels),  # Number of channels
                '-i', temp_raw_path,  # Input file
                '-c:a', 'libopus',  # Audio codec
                '-b:a', '64k',  # Audio bitrate
                '-y',  # Overwrite output file
                output_path
            ]
            
            self.logger.info(f"FFmpeg command: {' '.join(cmd)}")
            
            # Run FFmpeg
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=30
            )
            
            # Детальная диагностика результата FFmpeg
            self.logger.info(f"FFmpeg return code: {result.returncode}")
            if result.stdout:
                self.logger.info(f"FFmpeg stdout: {result.stdout}")
            if result.stderr:
                self.logger.info(f"FFmpeg stderr: {result.stderr}")
            
            # Clean up temp file
            os.unlink(temp_raw_path)
            
            if result.returncode == 0:
                # Проверим размер выходного файла
                if os.path.exists(output_path):
                    output_size = os.path.getsize(output_path)
                    self.logger.info(f"SUCCESS: Output webm file created: {output_path}, size: {output_size} bytes")
                    
                    if output_size < 1000:
                        self.logger.warning(f"WARNING: Output file very small: {output_size} bytes - possible silence")
                    
                    # Попробуем проанализировать webm файл с помощью ffprobe
                    try:
                        probe_cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_streams', output_path]
                        probe_result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=10)
                        if probe_result.returncode == 0:
                            self.logger.info(f"FFprobe output: {probe_result.stdout}")
                        else:
                            self.logger.warning(f"FFprobe failed: {probe_result.stderr}")
                    except Exception as e:
                        self.logger.warning(f"Could not run ffprobe: {e}")
                        
                else:
                    self.logger.error("ERROR: Output file doesn't exist after FFmpeg!")
                    return False
                return True
            else:
                self.logger.error(f"ERROR: FFmpeg failed with return code {result.returncode}")
                self.logger.error(f"FFmpeg stderr: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            self.logger.error("ERROR: FFmpeg conversion timed out")
            return False
        except Exception as e:
            self.logger.error(f"ERROR: Exception in PCM to webm conversion: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return False

    def has_data(self):
        """Check if there's remaining data in buffer"""
        has_data = len(self.pcm_buffer) > 0
        if has_data:
            self.logger.info(f"Buffer has {len(self.pcm_buffer)} samples remaining")
        return has_data

    def finalize_remaining(self):
        """Finalize any remaining data in buffer at end of session"""
        if len(self.pcm_buffer) == 0:
            self.logger.info("No remaining PCM data to finalize")
            return None, None, None
            
        self.logger.info(f"Finalizing remaining {len(self.pcm_buffer)} samples")
        
        # Use all remaining data
        chunk_data = self.pcm_buffer
        self.pcm_buffer = np.array([], dtype=np.float32)
        
        # Анализ оставшихся данных
        remaining_stats = {
            "samples": len(chunk_data),
            "duration_sec": len(chunk_data) / self.sample_rate,
            "min": chunk_data.min(),
            "max": chunk_data.max(),
            "max_amplitude": np.max(np.abs(chunk_data)),
            "zero_count": np.sum(chunk_data == 0)
        }
        
        self.logger.info(f"Remaining data stats: {remaining_stats}")
        
        timestamp = time.strftime('%Y-%m-%d_%H-%M-%S')
        webm_filename = f"chunk_final_{timestamp}_{self.chunk_count}.webm"
        webm_path = os.path.join(self.paths["audio"], webm_filename)
        
        success = self._pcm_to_webm(chunk_data, webm_path)
        
        if success:
            self.chunk_count += 1
            chunk_start_time = int(self.t0 * 1000)
            
            file_size = os.path.getsize(webm_path) if os.path.exists(webm_path) else 0
            self.logger.info(f"SUCCESS: Saved final PCM chunk as webm: {webm_path}, size: {file_size} bytes")
            
            return webm_path, timestamp, chunk_start_time
        else:
            self.logger.error("FAILED: Could not convert final PCM chunk to webm")
            return None, None, None