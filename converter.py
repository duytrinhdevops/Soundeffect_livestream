import os
import subprocess

SUPPORTED_VIDEO = (".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v")


def get_ffmpeg_path():
    base_dir = os.path.dirname(os.path.abspath(__file__))

    local_path = os.path.join(base_dir, "ffmpeg", "bin", "ffmpeg.exe")

    if os.path.exists(local_path):
        return local_path

    return "ffmpeg"  # fallback nếu máy có cài


FFMPEG_PATH = get_ffmpeg_path()


def convert_video_to_mp3(video_path, output_folder, bitrate="192k"):
    if not os.path.isfile(video_path):
        return False, f"Không tìm thấy video: {video_path}"

    os.makedirs(output_folder, exist_ok=True)

    name = os.path.splitext(os.path.basename(video_path))[0]
    output_path = os.path.join(output_folder, name + ".mp3")

    cmd = [
        FFMPEG_PATH,
        "-y",
        "-i", video_path,
        "-vn",
        "-codec:a", "libmp3lame",
        "-b:a", bitrate,
        output_path
    ]

    try:
        subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True
        )
        return True, output_path

    except Exception as e:
        return False, str(e)


def convert_folder_to_mp3(video_folder, output_folder, bitrate="192k"):
    if not os.path.isdir(video_folder):
        return {"success": 0, "failed": 0, "results": [], "message": "Folder không tồn tại"}

    videos = [f for f in os.listdir(video_folder) if f.lower().endswith(SUPPORTED_VIDEO)]

    success, failed = 0, 0
    results = []

    for v in videos:
        path = os.path.join(video_folder, v)
        ok, res = convert_video_to_mp3(path, output_folder, bitrate)

        print(("✅" if ok else "❌"), v)

        if ok:
            success += 1
        else:
            failed += 1

        results.append({"file": v, "ok": ok, "result": res})

    return {
        "success": success,
        "failed": failed,
        "results": results,
        "message": f"{success} OK / {failed} FAIL"
    }


if __name__ == "__main__":
    print("FFmpeg:", FFMPEG_PATH)

    inp = input("Video folder: ").strip().strip('"')
    out = input("Output folder: ").strip().strip('"')

    data = convert_folder_to_mp3(inp, out)

    print(data["message"])