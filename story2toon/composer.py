from __future__ import annotations

from pathlib import Path
import subprocess
import imageio_ffmpeg


def ffmpeg_exe():
    return imageio_ffmpeg.get_ffmpeg_exe()


def mux_audio(video_path: Path, audio_path: Path, output_path: Path, duration: float):
    cmd = [
        ffmpeg_exe(), "-y",
        "-i", str(video_path),
        "-i", str(audio_path),
        "-filter_complex", f"[1:a]apad=pad_dur={duration}[a]",
        "-map", "0:v:0", "-map", "[a]",
        "-t", str(duration),
        "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
        str(output_path),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    return output_path


def concatenate(scene_paths, output_path: Path):
    list_file = output_path.with_suffix(".concat.txt")
    list_file.write_text("\n".join(f"file '{Path(p).resolve().as_posix()}'" for p in scene_paths), encoding="utf-8")
    cmd = [
        ffmpeg_exe(), "-y", "-f", "concat", "-safe", "0",
        "-i", str(list_file), "-c", "copy", str(output_path)
    ]
    result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    if result.returncode != 0:
        # Re-encode if stream-copy concat fails on a platform/codec combination.
        cmd = [
            ffmpeg_exe(), "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(output_path)
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    return output_path
