#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import argparse
import subprocess
import sys
from pathlib import Path
import time

def apply_lut_to_video(video_path, lut_path, output_dir, quality="medium", crf=23):
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
    
    # Improved FFmpeg command for better compatibility and speed
    cmd = [
        "ffmpeg", "-i", video_path,
        "-vf", f"lut3d={lut_path}",
        "-c:v", "libx264", "-crf", str(crf),
        "-preset", quality,  # Quality preset
        "-pix_fmt", "yuv420p",  # More compatible pixel format
        "-c:a", "copy",
        "-map", "0:v:0",  # Only map main video stream
        "-map", "0:a?",   # Map audio if present
        "-ignore_unknown", # Ignore unknown streams
        "-progress", "pipe:1",  # Output progress information
        output_path
    ]
    
    print(f"Processing: {video_name}")
    if video_duration > 0:
        print(f"Video duration: {video_duration:.2f} seconds")
    
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
                progress_bar = f"[{'#' * (progress // 5)}{' ' * (20 - (progress // 5))}]"
                
                # Display progress information
                sys.stdout.write(f"\rProgress: {progress}% {progress_bar} Time: {int(elapsed//60):02d}:{int(elapsed%60):02d} {eta_str} Speed: {current_time/elapsed:.2f}x")
                sys.stdout.flush()
            
            # If we don't have duration info, show frame count and processing speed
            elif frame_count > 0:
                fps = frame_count / elapsed if elapsed > 0 else 0
                sys.stdout.write(f"\rProcessed frames: {frame_count} | FPS: {fps:.2f} | Time: {int(elapsed//60):02d}:{int(elapsed%60):02d}")
                sys.stdout.flush()
    
    # Get the return code
    return_code = process.poll()
    
    # Print a newline after progress bar
    print()
    
    # Check if there was an error
    if return_code != 0:
        stderr = process.stderr.read()
        print(f"Error processing {video_name}:")
        print(stderr)
        return None
    
    return output_path

def process_directory(input_dir, lut_path, quality="medium", crf=23):
    """Process all video files in the directory"""
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
    
    for i, video_file in enumerate(video_files, 1):
        print(f"\nFile {i}/{total_files}:")
        start_time = time.time()
        output_file = apply_lut_to_video(str(video_file), lut_path, output_dir, quality, crf)
        elapsed_time = time.time() - start_time
        
        if output_file:
            processed_files.append(output_file)
            print(f"Completed in {elapsed_time:.1f} seconds")
        else:
            failed_files.append(str(video_file))
    
    print(f"\nProcessing complete!")
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
    process_directory(args.input_dir, args.lut_file, args.quality, args.crf)

if __name__ == "__main__":
    main() 