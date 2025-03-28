#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import argparse
import subprocess
import sys
from pathlib import Path
import time
import concurrent.futures
import threading

def detect_hardware_encoders():
    """Detect available hardware encoders on the system"""
    encoders = {
        'nvidia': False,  # NVIDIA NVENC
        'amd': False,     # AMD AMF
        'qsv': False,     # Intel QuickSync
        'videotoolbox': False  # Apple VideoToolbox (Metal)
    }
    
    try:
        # Run ffmpeg to get encoder list
        cmd = ["ffmpeg", "-encoders", "-hide_banner"]
        output = subprocess.check_output(cmd, universal_newlines=True, stderr=subprocess.STDOUT)
        
        # Check for each encoder
        if " h264_nvenc " in output:
            encoders['nvidia'] = True
        if " h264_amf " in output:
            encoders['amd'] = True
        if " h264_qsv " in output:
            encoders['qsv'] = True
        if " h264_videotoolbox " in output:
            encoders['videotoolbox'] = True
            
        return encoders
    except:
        # If error occurs, return no encoders available
        return encoders

def apply_lut_to_video(video_path, lut_path, output_dir, quality="medium", crf=23, hw_encoder=None, print_lock=None, task_id=0):
    """Apply LUT to a single video"""
    video_name = os.path.basename(video_path)
    name, ext = os.path.splitext(video_name)
    output_path = os.path.join(output_dir, f"{name}_LUT{ext}")
    
    # First, get video duration using ffprobe
    duration_cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", video_path
    ]
    
    try:
        video_duration = float(subprocess.check_output(duration_cmd, universal_newlines=True).strip())
    except:
        video_duration = 0
    
    # Base FFmpeg command
    cmd = [
        "ffmpeg", "-i", video_path,
        "-vf", f"lut3d={lut_path}",
    ]
    
    # Add encoder settings based on hardware availability
    if hw_encoder == 'nvidia':
        # NVIDIA NVENC
        cmd.extend([
            "-c:v", "h264_nvenc",
            "-preset", "p4" if quality in ["veryslow", "slower", "slow"] else 
                      "p2" if quality == "medium" else "p1",
            "-profile:v", "high",
            "-rc", "vbr",
            "-cq", str(crf),
            "-b:v", "0",  # Use CQ mode
        ])
    elif hw_encoder == 'amd':
        # AMD AMF
        cmd.extend([
            "-c:v", "h264_amf",
            "-quality", "quality" if quality in ["veryslow", "slower", "slow", "medium"] else "speed",
            "-rc", "cqp",
            "-qp_i", str(crf),
            "-qp_p", str(crf),
        ])
    elif hw_encoder == 'qsv':
        # Intel QuickSync
        cmd.extend([
            "-c:v", "h264_qsv",
            "-preset", "veryslow" if quality in ["veryslow", "slower"] else 
                       "slower" if quality == "slow" else 
                       "medium" if quality == "medium" else "faster",
            "-global_quality", str(crf),
        ])
    elif hw_encoder == 'videotoolbox':
        # Apple VideoToolbox (Metal)
        cmd.extend([
            "-c:v", "h264_videotoolbox",
            "-q:v", str(max(1, min(100, (51-crf)*2))),  # Convert CRF to q value (1-100)
            "-allow_sw", "1",  # Allow software processing if needed
        ])
    else:
        # Software encoding (libx264)
        cmd.extend([
            "-c:v", "libx264",
            "-crf", str(crf),
            "-preset", quality,
        ])
    
    # Common settings for all encoders
    cmd.extend([
        "-pix_fmt", "yuv420p",  # More compatible pixel format
        "-c:a", "copy",
        "-map", "0:v:0",  # Only map main video stream
        "-map", "0:a?",   # Map audio if present
        "-ignore_unknown", # Ignore unknown streams
        "-progress", "pipe:1",  # Output progress information
        output_path
    ])
    
    # Use print_lock if provided
    if print_lock:
        with print_lock:
            if hw_encoder:
                print(f"[{video_name}] Hardware encoder: {hw_encoder}")
            else:
                print(f"[{video_name}] Software encoder (libx264)")
    else:
        if hw_encoder:
            print(f"[{video_name}] Hardware encoder: {hw_encoder}")
        else:
            print(f"[{video_name}] Software encoder (libx264)")
    
    # Start the process
    process = subprocess.Popen(
        cmd, 
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True
    )
    
    # Variables to track progress
    duration = video_duration if video_duration > 0 else None
    current_time = 0
    frame_count = 0
    total_frames = 0
    start_time = time.time()
    last_update_time = start_time
    
    # Process output in real-time to show progress
    while True:
        line = process.stdout.readline()
        if not line and process.poll() is not None:
            break
            
        # Parse progress information
        if line.startswith("out_time_ms="):
            try:
                time_str = line.split("=")[1].strip()
                if time_str != "N/A":
                    current_time = int(time_str) / 1000000  # Convert to seconds
            except (ValueError, IndexError):
                pass
        elif line.startswith("frame="):
            try:
                frame_str = line.split("=")[1].strip()
                if frame_str != "N/A":
                    frame_count = int(frame_str)
            except (ValueError, IndexError):
                pass
        elif line.startswith("fps="):
            try:
                fps_str = line.split("=")[1].strip()
                if fps_str != "N/A":
                    current_fps = float(fps_str)
            except (ValueError, IndexError):
                current_fps = 0
                
        # Update progress display every 0.5 seconds
        current_update_time = time.time()
        if current_update_time - last_update_time >= 0.5:
            last_update_time = current_update_time
            elapsed = current_update_time - start_time
            
            # Calculate progress percentage
            if duration and duration > 0 and current_time > 0:
                progress = min(100, int(current_time / duration * 100))
                
                # Calculate ETA
                if progress > 0:
                    eta = (elapsed / progress) * (100 - progress)
                    eta_str = f"ETA: {int(eta//60):02d}:{int(eta%60):02d}"
                else:
                    eta_str = "ETA: --:--"
                
                # Create progress bar
                bar_length = 20
                filled_length = progress // 5  # 每5%填充一个字符
                progress_bar = f"[{'#' * filled_length}{' ' * (bar_length - filled_length)}]"
                
                # Display progress information with lock and task_id for positioning
                progress_str = f"{video_name}: {progress}% {progress_bar} Time: {int(elapsed//60):02d}:{int(elapsed%60):02d} {eta_str}"
                
                if print_lock:
                    with print_lock:
                        # Move cursor to task's line and clear it
                        sys.stdout.write(f"\033[{task_id};0H\033[K{progress_str}")
                        sys.stdout.flush()
                else:
                    sys.stdout.write(f"\r{progress_str}")
                    sys.stdout.flush()
            
            # If we don't have duration info, show frame count and processing speed
            elif frame_count > 0:
                fps = frame_count / elapsed if elapsed > 0 else 0
                progress_str = f"{video_name}: Processed frames: {frame_count} | FPS: {fps:.2f} | Time: {int(elapsed//60):02d}:{int(elapsed%60):02d}"
                
                if print_lock:
                    with print_lock:
                        # Move cursor to task's line and clear it
                        sys.stdout.write(f"\033[{task_id};0H\033[K{progress_str}")
                        sys.stdout.flush()
                else:
                    sys.stdout.write(f"\r{progress_str}")
                    sys.stdout.flush()
    
    # Get the return code
    return_code = process.poll()
    
    # Print final status
    if print_lock:
        with print_lock:
            # Move cursor to task's line and clear it
            sys.stdout.write(f"\033[{task_id};0H\033[K{video_name}: {'Completed' if return_code == 0 else 'Failed'}")
            sys.stdout.flush()
    else:
        print()
    
    # Check if there was an error
    if return_code != 0:
        stderr = process.stderr.read()
        if print_lock:
            with print_lock:
                print(f"\n\nError processing {video_name}:")
                print(stderr)
        else:
            print(f"Error processing {video_name}:")
            print(stderr)
        return None
    
    return output_path

def process_directory(input_dir, lut_path, quality="medium", crf=23, max_workers=None, use_gpu=True):
    """Process all video files in the directory"""
    # Detect hardware encoders if GPU is enabled
    hw_encoder = None
    if use_gpu:
        encoders = detect_hardware_encoders()
        if encoders['nvidia']:
            hw_encoder = 'nvidia'
            print("NVIDIA GPU encoder (NVENC) detected and will be used")
        elif encoders['amd']:
            hw_encoder = 'amd'
            print("AMD GPU encoder (AMF) detected and will be used")
        elif encoders['videotoolbox']:
            hw_encoder = 'videotoolbox'
            print("Apple VideoToolbox (Metal) detected and will be used")
        elif encoders['qsv']:
            hw_encoder = 'qsv'
            print("Intel QuickSync encoder detected and will be used")
        else:
            print("No hardware encoders detected, falling back to CPU encoding")
    else:
        print("Hardware acceleration disabled, using CPU encoding")
    
    # Supported video formats
    video_extensions = ['.mp4', '.mov', '.avi', '.mkv']
    
    # Output directory is the same as input directory
    output_dir = input_dir
    
    # Get all video files
    video_files = []
    for ext in video_extensions:
        video_files.extend(Path(input_dir).glob(f"*{ext}"))
        video_files.extend(Path(input_dir).glob(f"*{ext.upper()}"))
    
    if not video_files:
        print(f"No video files found in {input_dir}")
        return
    
    # Process each video file
    processed_files = []
    failed_files = []
    
    total_files = len(video_files)
    print(f"Found {total_files} video files to process")
    
    # Determine number of worker threads
    if max_workers is None:
        # Default to number of CPUs if not specified
        max_workers = os.cpu_count()
    max_workers = min(max_workers, total_files)  # Don't use more workers than files
    print(f"Using {max_workers} worker threads")
    
    # Create a lock for thread-safe printing
    print_lock = threading.Lock()
    
    # Setup terminal for multi-line progress display
    with print_lock:
        # Clear screen and hide cursor
        sys.stdout.write("\033[2J\033[H\033[?25l")
        sys.stdout.flush()
        
        # Print header
        print(f"Processing {total_files} video files with {max_workers} workers")
        print("=" * 80)
        
        # Print empty lines for each task
        for i in range(max_workers + 1):
            print()
    
    def process_video(video_file, file_index):
        nonlocal processed_files, failed_files
        video_name = os.path.basename(video_file)
        
        # Assign a line number for this task (add offset for header lines)
        task_line = (file_index % max_workers) + 3  # +3 for header lines
        
        with print_lock:
            sys.stdout.write(f"\033[{task_line};0H\033[KStarting: {video_name}")
            sys.stdout.flush()
        
        start_time = time.time()
        output_file = apply_lut_to_video(str(video_file), lut_path, output_dir, quality, crf, hw_encoder, print_lock, task_line)
        elapsed_time = time.time() - start_time
        
        with print_lock:
            # Move to task line and update with completion status
            sys.stdout.write(f"\033[{task_line};0H\033[K{video_name}: {'Completed' if output_file else 'Failed'} in {elapsed_time:.1f} seconds")
            sys.stdout.flush()
            
            # Move to summary line and update counts
            summary_line = max_workers + 4
            sys.stdout.write(f"\033[{summary_line};0H\033[KCompleted: {len(processed_files)}/{total_files} | Failed: {len(failed_files)}")
            sys.stdout.flush()
            
            if output_file:
                processed_files.append(output_file)
            else:
                failed_files.append(str(video_file))
    
    # Use ThreadPoolExecutor to process videos in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(process_video, video_file, i) for i, video_file in enumerate(video_files, 1)]
        concurrent.futures.wait(futures)
    
    # Restore terminal and show cursor
    with print_lock:
        sys.stdout.write("\033[?25h")  # Show cursor
        sys.stdout.flush()
    
    # Print final summary
    print("\n\nProcessing complete!")
    print(f"Successfully processed: {len(processed_files)} files")
    if failed_files:
        print(f"Failed to process: {len(failed_files)} files")
        for f in failed_files:
            print(f" - {os.path.basename(f)}")
    
    print(f"Output files saved to: {output_dir}")

def main():
    parser = argparse.ArgumentParser(description='Batch apply DJI LUT to video files')
    parser.add_argument('input_dir', help='Input directory containing video files')
    parser.add_argument('lut_file', help='LUT file path (.cube format)')
    parser.add_argument('-q', '--quality', 
                        choices=['ultrafast', 'superfast', 'veryfast', 'faster', 'fast', 'medium', 'slow', 'slower', 'veryslow'],
                        default='medium',
                        help='Encoding quality/speed (default: medium)')
    parser.add_argument('-c', '--crf', type=int, default=23, 
                        help='CRF value for quality (0-51, lower is better quality, default: 23)')
    parser.add_argument('-t', '--threads', type=int, default=None,
                        help='Maximum number of parallel processing threads (default: CPU count)')
    parser.add_argument('-g', '--gpu', action='store_true', default=True,
                        help='Enable GPU acceleration if available (default: enabled)')
    parser.add_argument('--no-gpu', action='store_false', dest='gpu',
                        help='Disable GPU acceleration')
    
    args = parser.parse_args()
    
    # Check if input directory exists
    if not os.path.isdir(args.input_dir):
        print(f"Error: Input directory '{args.input_dir}' does not exist")
        return
    
    # Check if LUT file exists and is in .cube format
    if not os.path.isfile(args.lut_file) or not args.lut_file.lower().endswith('.cube'):
        print(f"Error: LUT file '{args.lut_file}' does not exist or is not in .cube format")
        return
    
    # Validate CRF value
    if args.crf < 0 or args.crf > 51:
        print(f"Error: CRF value must be between 0 and 51")
        return
    
    # Process video files
    process_directory(args.input_dir, args.lut_file, args.quality, args.crf, args.threads, args.gpu)

if __name__ == "__main__":
    main() 