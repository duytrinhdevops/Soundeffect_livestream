import customtkinter as ctk
import pygame
import threading
import os
import shutil
import json
from tkinter import filedialog, messagebox

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    DND_AVAILABLE = True
except Exception:
    DND_FILES = None
    TkinterDnD = None
    DND_AVAILABLE = False


try:
    from converter import convert_video_to_mp3, SUPPORTED_VIDEO
except Exception:
    convert_video_to_mp3 = None
    SUPPORTED_VIDEO = (".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v")


class CTkDnD(ctk.CTk, TkinterDnD.DnDWrapper if DND_AVAILABLE else object):
    """
    Giữ giao diện CustomTkinter giống bản cũ,
    nhưng vẫn hỗ trợ kéo-thả file bằng tkinterdnd2.
    """
    def __init__(self, *args, **kwargs):
        ctk.CTk.__init__(self, *args, **kwargs)

        if DND_AVAILABLE:
            try:
                self.TkdndVersion = TkinterDnD._require(self)
            except Exception as e:
                print("Không load được TkinterDnD:", e)


# ================= CONFIG =================

SUPPORTED_AUDIO = (".mp3", ".wav", ".ogg")
SOUNDS_ROOT = "sounds"
SETTINGS_FILE = "settings.json"
DELETED_BOARDS_ROOT = "deleted_boards"

buttons = []
sound_button_data = []
current_board = 0
current_sound = None
current_channel = None
current_playing_path = None
is_paused = False

pygame.mixer.init()


# ================= SETTINGS DATA =================

def load_settings():
    default_data = {
        "volume": 0.8,
        "last_board": 0,
        "window_size": "660x540",
        "grid_cols": 4,
        "grid_rows": 3
    }

    if not os.path.exists(SETTINGS_FILE):
        return default_data

    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        for key, value in default_data.items():
            data.setdefault(key, value)

        return data
    except Exception:
        return default_data


SETTINGS = load_settings()
volume = float(SETTINGS.get("volume", 0.8))
GRID_COLS = int(SETTINGS.get("grid_cols", 4))
GRID_ROWS = int(SETTINGS.get("grid_rows", 3))
MAX_SOUNDS = GRID_COLS * GRID_ROWS


def save_settings():
    data = {
        "volume": volume,
        "last_board": current_board,
        "window_size": app.geometry(),
        "grid_cols": GRID_COLS,
        "grid_rows": GRID_ROWS
    }

    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print("Lỗi lưu settings:", e)


# ================= BOARDS DATA =================

def ensure_default_folders():
    os.makedirs(SOUNDS_ROOT, exist_ok=True)
    default_folders = ["Bang1", "Bang2"]

    for folder in default_folders:
        os.makedirs(os.path.join(SOUNDS_ROOT, folder), exist_ok=True)


def load_boards_from_folders():
    boards = []
    ensure_default_folders()

    for folder_name in sorted(os.listdir(SOUNDS_ROOT), key=str.lower):
        folder_path = os.path.join(SOUNDS_ROOT, folder_name)

        if os.path.isdir(folder_path):
            boards.append({
                "name": folder_name,
                "folder": folder_path
            })

    return boards


BOARDS = load_boards_from_folders()


# ================= SOUND LOADER =================

def load_sounds(folder):
    sounds = []
    os.makedirs(folder, exist_ok=True)

    for file in sorted(os.listdir(folder), key=str.lower):
        if file.lower().endswith(SUPPORTED_AUDIO):
            sounds.append({
                "name": os.path.splitext(file)[0],
                "file": os.path.join(folder, file)
            })

    return sounds


# ================= AUDIO =================

def play_sound(path):
    global current_sound, current_channel, current_playing_path, is_paused, is_paused

    if not os.path.exists(path):
        print("Không tìm thấy:", path)
        return

    try:
        pygame.mixer.stop()

        current_sound = pygame.mixer.Sound(path)
        current_sound.set_volume(volume)

        current_channel = current_sound.play()
        is_paused = False
        app.after(0, lambda: pause_btn.configure(text="⏸ Pause"))
        current_playing_path = path
        app.after(0, update_sound_highlight)

        if current_channel:
            current_channel.set_volume(volume)

    except Exception as e:
        print("Lỗi phát âm thanh:", e)


def play_thread(path):
    threading.Thread(target=play_sound, args=(path,), daemon=True).start()


def stop_sound():
    global current_sound, current_channel, current_playing_path, is_paused

    pygame.mixer.stop()
    current_sound = None
    current_channel = None
    current_playing_path = None
    is_paused = False
    update_sound_highlight()
    is_paused = False
    try:
        pause_btn.configure(text="⏸ Pause")
    except:
        pass


def set_volume(v):
    global volume, current_sound, current_channel

    volume = float(v)

    if current_sound:
        current_sound.set_volume(volume)

    if current_channel:
        current_channel.set_volume(volume)

    volume_label.configure(text=f"Volume: {int(volume * 100)}%")
    save_settings()



def toggle_pause():
    global is_paused

    if not current_channel:
        return

    if is_paused:
        pygame.mixer.unpause()
        is_paused = False
        pause_btn.configure(text="⏸ Pause")
    else:
        pygame.mixer.pause()
        is_paused = True
        pause_btn.configure(text="▶ Resume")

# ================= TEXT / GRID HELPERS =================

def fit_text_to_button(text, width, height):
    text = str(text).strip()

    width = max(int(width), 70)
    height = max(int(height), 45)

    # Ô càng nhỏ font càng nhỏ, ô lớn font lớn hơn.
    font_size = int(min(width / 8.2, height / 4.8))
    font_size = max(8, min(font_size, 14))

    # Ước lượng số ký tự vừa với chiều ngang ô.
    max_chars = int((width - 18) / (font_size * 0.55))
    max_chars = max(5, max_chars)

    if len(text) > max_chars:
        if max_chars <= 3:
            display = text[:max_chars]
        else:
            display = text[:max_chars - 3] + "..."
    else:
        display = text

    return display, ("Arial", font_size, "bold")


def update_one_sound_button(btn, full_name):
    try:
        width = btn.winfo_width()
        height = btn.winfo_height()
        display, font = fit_text_to_button(full_name, width, height)
        btn.configure(text=display, font=font)

        if hasattr(btn, "_text_label"):
            btn._text_label.configure(
                wraplength=0,
                justify="center",
                anchor="center"
            )
    except Exception:
        pass


def update_all_sound_button_texts():
    for btn, full_name, path in sound_button_data:
        update_one_sound_button(btn, full_name)
    update_sound_highlight()


def update_sound_highlight():
    for btn, full_name, path in sound_button_data:
        try:
            if path == current_playing_path:
                btn.configure(
                    fg_color="#16a34a",
                    hover_color="#15803d",
                    border_width=2,
                    border_color="#bbf7d0"
                )
            else:
                btn.configure(
                    fg_color="#1f538d",
                    hover_color="#14375e",
                    border_width=0
                )
        except Exception:
            pass



# ================= DRAG & DROP HELPERS =================

def parse_drop_files(raw_data):
    """
    Windows drag-drop có thể trả về dạng:
    {E:/a b/file.mp3} E:/test.wav
    Hàm này tách đúng path kể cả khi có dấu cách.
    """
    files = []
    current = ""
    in_brace = False

    for ch in raw_data:
        if ch == "{":
            in_brace = True
            current = ""
        elif ch == "}":
            in_brace = False
            if current:
                files.append(current)
                current = ""
        elif ch == " " and not in_brace:
            if current:
                files.append(current)
                current = ""
        else:
            current += ch

    if current:
        files.append(current)

    return [f.strip().strip('"') for f in files if f.strip()]


def add_audio_files_to_current_board(paths, show_result=True):
    """
    Thêm file âm thanh vào bảng hiện tại.
    Bổ sung: nếu kéo-thả file video .mp4/.mov/.mkv/.avi/.webm/.m4v
    thì app sẽ tự convert sang MP3 và lưu thẳng vào folder bảng hiện tại.
    """
    if not BOARDS:
        if show_result:
            messagebox.showwarning("Lỗi", "Chưa có bảng âm thanh nào")
        return

    folder = BOARDS[current_board]["folder"]
    os.makedirs(folder, exist_ok=True)

    added = 0
    converted = 0
    skipped = 0
    failed = 0
    failed_details = []

    for path in paths:
        path = path.strip().strip('"')

        if not os.path.isfile(path):
            skipped += 1
            continue

        lower_path = path.lower()

        # 1) Nếu là audio thì copy như cũ
        if lower_path.endswith(SUPPORTED_AUDIO):
            file_name = os.path.basename(path)
            new_path = os.path.join(folder, file_name)

            if os.path.exists(new_path):
                skipped += 1
                continue

            try:
                shutil.copy2(path, new_path)
                added += 1
            except Exception as e:
                failed += 1
                failed_details.append(f"{os.path.basename(path)}: {e}")

        # 2) Nếu là video thì convert sang MP3 và thêm luôn vào bảng
        elif lower_path.endswith(SUPPORTED_VIDEO):
            if convert_video_to_mp3 is None:
                failed += 1
                failed_details.append(
                    f"{os.path.basename(path)}: chưa có converter.py hoặc chưa import được convert_video_to_mp3"
                )
                continue

            try:
                ok, result = convert_video_to_mp3(path, folder)

                if ok:
                    converted += 1
                else:
                    failed += 1
                    failed_details.append(f"{os.path.basename(path)}: {result}")
            except Exception as e:
                failed += 1
                failed_details.append(f"{os.path.basename(path)}: {e}")

        # 3) File khác thì bỏ qua
        else:
            skipped += 1

    def done_ui():
        refresh_grid()

        if show_result:
            msg = (
                f"Đã thêm audio: {added} file\n"
                f"Đã convert video: {converted} file\n"
                f"Bỏ qua: {skipped} file\n"
                f"Lỗi: {failed} file"
            )

            if failed_details:
                msg += "\n\nChi tiết lỗi:\n" + "\n".join(failed_details[:5])
                if len(failed_details) > 5:
                    msg += f"\n... và {len(failed_details) - 5} lỗi khác"

            messagebox.showinfo("Kéo thả âm thanh / video", msg)

    try:
        app.after(0, done_ui)
    except Exception:
        done_ui()

def handle_drop_audio(event):
    paths = parse_drop_files(event.data)

    # Convert video có thể hơi nặng, chạy ở thread riêng để app không bị đơ.
    def worker():
        add_audio_files_to_current_board(paths)

    threading.Thread(target=worker, daemon=True).start()


def enable_drag_drop(widget):
    if not DND_AVAILABLE:
        return

    try:
        widget.drop_target_register(DND_FILES)
        widget.dnd_bind("<<Drop>>", handle_drop_audio)
    except Exception as e:
        print("Không bật được kéo-thả:", e)


# ================= UI UPDATE =================

def refresh_board_buttons():
    for widget in board_btn_frame.winfo_children():
        widget.destroy()

    for i, board in enumerate(BOARDS):
        is_selected = i == current_board
        btn = ctk.CTkButton(
            board_btn_frame,
            text=board["name"],
            font=("Segoe UI", 14, "bold"),
            width=110,
            height=38,
            fg_color="#2563eb" if is_selected else "#1f2937",
            hover_color="#1d4ed8" if is_selected else "#374151",
            border_width=2 if is_selected else 0,
            border_color="#bfdbfe",
            command=lambda index=i: switch_board(index)
        )
        btn.pack(side="left", padx=5, pady=5)


def switch_board(index):
    global current_board

    if not BOARDS:
        return

    if index >= len(BOARDS):
        index = 0

    current_board = index

    board_title.configure(
        text=f"{BOARDS[current_board]['name']}  |  {BOARDS[current_board]['folder']}"
    )

    refresh_grid()
    refresh_board_buttons()
    save_settings()


def clear_grid_config():
    for i in range(20):
        grid_frame.grid_columnconfigure(i, weight=0, minsize=0, uniform="")
        grid_frame.grid_rowconfigure(i, weight=0, minsize=0, uniform="")


def refresh_grid():
    global buttons, sound_button_data

    for btn in buttons:
        btn.destroy()

    buttons = []
    sound_button_data = []

    clear_grid_config()

    if not BOARDS:
        return

    for i in range(GRID_COLS):
        grid_frame.grid_columnconfigure(i, weight=1, uniform="sound_cols")

    for i in range(GRID_ROWS):
        grid_frame.grid_rowconfigure(i, weight=1, uniform="sound_rows")

    folder = BOARDS[current_board]["folder"]
    sounds = load_sounds(folder)
    limit = GRID_COLS * GRID_ROWS

    for i, sound in enumerate(sounds[:limit]):
        row = i // GRID_COLS
        col = i % GRID_COLS

        btn = ctk.CTkButton(
            grid_frame,
            text="",
            height=64,
            width=90,
            anchor="center",
            command=lambda p=sound["file"]: play_thread(p)
        )

        btn.grid(
            row=row,
            column=col,
            padx=5,
            pady=5,
            sticky="nsew"
        )

        sound_button_data.append((btn, sound["name"], sound["file"]))
        btn.bind("<Configure>", lambda event, b=btn, name=sound["name"]: update_one_sound_button(b, name))

        buttons.append(btn)

    app.after(80, update_all_sound_button_texts)


def reload_boards():
    global BOARDS, current_board

    old_board_name = BOARDS[current_board]["name"] if BOARDS else None
    BOARDS = load_boards_from_folders()

    if not BOARDS:
        return

    refresh_board_buttons()

    new_index = 0
    if old_board_name:
        for i, board in enumerate(BOARDS):
            if board["name"] == old_board_name:
                new_index = i
                break

    switch_board(new_index)


def reload_current_board():
    refresh_grid()


# ================= SETTINGS WINDOW =================

def open_settings():
    settings = ctk.CTkToplevel(app)
    settings.title("⚙ Cài đặt")
    settings.geometry("500x650")
    settings.resizable(False, True)
    settings.grab_set()

    page_container = ctk.CTkFrame(settings, fg_color="transparent")
    page_container.pack(fill="both", expand=True, padx=10, pady=10)

    board_name_var = ctk.StringVar()
    video_folder_var = ctk.StringVar()
    output_folder_var = ctk.StringVar()

    def clear_page():
        for widget in page_container.winfo_children():
            widget.destroy()

    def show_back_title(title_text):
        top = ctk.CTkFrame(page_container, fg_color="transparent")
        top.pack(fill="x", pady=(0, 10))

        ctk.CTkButton(
            top,
            text="← Quay lại",
            width=100,
            command=show_main_menu
        ).pack(side="left")

        ctk.CTkLabel(
            top,
            text=title_text,
            font=("Arial", 20, "bold")
        ).pack(side="left", padx=15)

    def show_main_menu():
        clear_page()

        ctk.CTkLabel(
            page_container,
            text="⚙ Cài đặt Soundboard",
            font=("Arial", 24, "bold")
        ).pack(pady=25)

        ctk.CTkButton(
            page_container,
            text="🎵 Quản lý âm thanh",
            height=50,
            command=show_add_sound_page
        ).pack(fill="x", padx=30, pady=10)

        ctk.CTkButton(
            page_container,
            text="🎬 Convert video sang MP3",
            height=50,
            fg_color="#16a34a",
            hover_color="#15803d",
            command=show_convert_page
        ).pack(fill="x", padx=30, pady=10)

        ctk.CTkButton(
            page_container,
            text="📁 Quản lý bảng",
            height=50,
            command=show_board_page
        ).pack(fill="x", padx=30, pady=10)

        ctk.CTkButton(
            page_container,
            text="🔢 Tuỳ chỉnh hàng / cột",
            height=50,
            command=show_grid_settings_page
        ).pack(fill="x", padx=30, pady=10)

        ctk.CTkButton(
            page_container,
            text="Đóng",
            height=45,
            fg_color="#b91c1c",
            hover_color="#7f1d1d",
            command=settings.destroy
        ).pack(fill="x", padx=30, pady=30)

    def show_add_sound_page():
        clear_page()
        show_back_title("🎵 Quản lý âm thanh")

        if not BOARDS:
            messagebox.showwarning("Lỗi", "Chưa có bảng âm thanh nào")
            return

        folder = BOARDS[current_board]["folder"]

        top_frame = ctk.CTkFrame(page_container)
        top_frame.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(
            top_frame,
            text=f"Bảng hiện tại: {BOARDS[current_board]['name']}",
            font=("Arial", 16, "bold")
        ).pack(pady=8)

        list_frame = ctk.CTkScrollableFrame(page_container)
        list_frame.pack(fill="both", expand=True, padx=20, pady=10)

        def refresh_sound_list():
            for w in list_frame.winfo_children():
                w.destroy()

            files = [
                f for f in sorted(os.listdir(folder), key=str.lower)
                if f.lower().endswith(SUPPORTED_AUDIO)
            ]

            if not files:
                ctk.CTkLabel(
                    list_frame,
                    text="Chưa có file âm thanh nào trong bảng này",
                    font=("Arial", 14)
                ).pack(pady=20)
                return

            for file in files:
                path = os.path.join(folder, file)

                row = ctk.CTkFrame(list_frame)
                row.pack(fill="x", pady=5)

                label = ctk.CTkLabel(
                    row,
                    text=file,
                    anchor="w",
                    font=("Inter", 11, "bold")
                )
                label.pack(side="left", fill="x", expand=True, padx=10, pady=8)

                def rename_sound(f=file, p=path, r=row):
                    for c in r.winfo_children():
                        c.destroy()

                    name_no_ext, ext = os.path.splitext(f)
                    var = ctk.StringVar(value=name_no_ext)

                    entry = ctk.CTkEntry(r, textvariable=var)
                    entry.pack(side="left", fill="x", expand=True, padx=10, pady=5)
                    entry.focus()

                    def save():
                        new_name = var.get().strip()

                        if not new_name:
                            refresh_sound_list()
                            return

                        new_file = new_name + ext
                        new_path = os.path.join(folder, new_file)

                        if new_path == p:
                            refresh_sound_list()
                            return

                        if os.path.exists(new_path):
                            messagebox.showwarning("Lỗi", "Tên file đã tồn tại")
                            refresh_sound_list()
                            return

                        try:
                            os.rename(p, new_path)
                            refresh_sound_list()
                            refresh_grid()
                        except Exception as e:
                            messagebox.showerror("Lỗi", f"Không đổi tên được file:\n{e}")
                            refresh_sound_list()

                    def cancel():
                        refresh_sound_list()

                    entry.bind("<Return>", lambda e: save())
                    entry.bind("<Escape>", lambda e: cancel())

                    ctk.CTkButton(r, text="Lưu", width=60, command=save).pack(side="right", padx=5)
                    ctk.CTkButton(r, text="Huỷ", width=60, command=cancel).pack(side="right", padx=5)

                def delete_sound(f=file, p=path):
                    confirm = messagebox.askyesno(
                        "Xác nhận xoá",
                        f"Bạn có chắc muốn xoá file âm thanh này không?\n\n{f}"
                    )

                    if not confirm:
                        return

                    try:
                        os.remove(p)
                        refresh_sound_list()
                        refresh_grid()
                    except Exception as e:
                        messagebox.showerror("Lỗi", f"Không xoá được file:\n{e}")

                ctk.CTkButton(row, text="▶", width=45, command=lambda p=path: play_thread(p)).pack(side="right", padx=4)
                ctk.CTkButton(row, text="✏️", width=45, command=lambda f=file, p=path, r=row: rename_sound(f, p, r)).pack(side="right", padx=4)
                ctk.CTkButton(row, text="🗑", width=45, fg_color="#b91c1c", hover_color="#7f1d1d", command=lambda f=file, p=path: delete_sound(f, p)).pack(side="right", padx=4)

        def choose_audio_file():
            path = filedialog.askopenfilename(
                title="Chọn file âm thanh",
                filetypes=[
                    ("Audio Files", "*.mp3 *.wav *.ogg"),
                    ("MP3", "*.mp3"),
                    ("WAV", "*.wav"),
                    ("OGG", "*.ogg"),
                ]
            )

            if not path:
                return

            add_audio_files_to_current_board([path], show_result=False)
            refresh_sound_list()
            messagebox.showinfo("Thành công", "Đã thêm âm thanh vào bảng hiện tại")

        ctk.CTkButton(top_frame, text="➕ Thêm file mp3 / wav / ogg", command=choose_audio_file).pack(fill="x", padx=15, pady=8)

        ctk.CTkLabel(
            top_frame,
            text="Bạn cũng có thể kéo thả file mp3 / wav / ogg trực tiếp vào cửa sổ app." if DND_AVAILABLE else "Kéo-thả chưa bật. Cài: python -m pip install tkinterdnd2",
            font=("Segoe UI", 11),
            text_color="#9ca3af",
            wraplength=380
        ).pack(fill="x", padx=15, pady=(0, 8))
        ctk.CTkButton(top_frame, text="🔄 Load lại danh sách âm thanh", command=refresh_sound_list).pack(fill="x", padx=15, pady=8)

        refresh_sound_list()

    def show_convert_page():
        clear_page()
        show_back_title("🎬 Convert video sang MP3")

        frame = ctk.CTkFrame(page_container)
        frame.pack(fill="x", padx=20, pady=20)

        def choose_video_folder():
            folder = filedialog.askdirectory(title="Chọn thư mục chứa video")
            if folder:
                video_folder_var.set(folder)

        def choose_output_folder():
            folder = filedialog.askdirectory(title="Chọn thư mục lưu MP3")
            if folder:
                output_folder_var.set(folder)

        def use_current_board_as_output():
            if BOARDS:
                output_folder_var.set(BOARDS[current_board]["folder"])

        ctk.CTkEntry(frame, textvariable=video_folder_var, placeholder_text="Thư mục chứa video TikTok").pack(fill="x", padx=15, pady=8)
        ctk.CTkButton(frame, text="📂 Chọn thư mục video", command=choose_video_folder).pack(fill="x", padx=15, pady=8)
        ctk.CTkEntry(frame, textvariable=output_folder_var, placeholder_text="Thư mục lưu MP3").pack(fill="x", padx=15, pady=8)
        ctk.CTkButton(frame, text="🎵 Lưu MP3 vào bảng hiện tại", command=use_current_board_as_output).pack(fill="x", padx=15, pady=8)
        ctk.CTkButton(frame, text="📁 Chọn thư mục lưu MP3 khác", command=choose_output_folder).pack(fill="x", padx=15, pady=8)

        convert_status = ctk.CTkLabel(frame, text="Chưa convert", font=("Arial", 13))
        convert_status.pack(pady=8)

        progress_bar = ctk.CTkProgressBar(frame)
        progress_bar.set(0)
        progress_bar.pack(fill="x", padx=15, pady=6)

        log_box = ctk.CTkTextbox(frame, height=170)
        log_box.pack(fill="both", expand=True, padx=15, pady=8)
        log_box.insert("end", "Log convert sẽ hiện ở đây...\n")
        log_box.configure(state="disabled")

        def append_log(text):
            log_box.configure(state="normal")
            log_box.insert("end", text + "\n")
            log_box.see("end")
            log_box.configure(state="disabled")

        def convert_video_folder():
            video_folder = video_folder_var.get().strip()
            output_folder = output_folder_var.get().strip()

            if convert_video_to_mp3 is None:
                messagebox.showerror("Lỗi", "Không import được convert_video_to_mp3 từ converter.py")
                return

            if not video_folder:
                messagebox.showwarning("Thiếu thư mục", "Bạn chưa chọn thư mục chứa video")
                return

            if not output_folder:
                messagebox.showwarning("Thiếu thư mục", "Bạn chưa chọn thư mục lưu MP3")
                return

            if not os.path.isdir(video_folder):
                messagebox.showwarning("Lỗi", "Thư mục video không tồn tại")
                return

            videos = [
                f for f in sorted(os.listdir(video_folder), key=str.lower)
                if f.lower().endswith(SUPPORTED_VIDEO)
            ]

            if not videos:
                messagebox.showinfo("Không có video", "Không tìm thấy video nào trong thư mục")
                return

            convert_btn.configure(state="disabled", text="⏳ Đang convert...")
            convert_status.configure(text=f"Chuẩn bị convert {len(videos)} file...")
            progress_bar.set(0)

            log_box.configure(state="normal")
            log_box.delete("1.0", "end")
            log_box.configure(state="disabled")

            def worker():
                success = 0
                failed = 0
                total = len(videos)

                for index, video in enumerate(videos, start=1):
                    video_path = os.path.join(video_folder, video)

                    app.after(0, lambda i=index, t=total, v=video: (
                        convert_status.configure(text=f"Đang convert ({i}/{t}): {v}"),
                        progress_bar.set((i - 1) / t),
                        append_log(f"⏳ ({i}/{t}) Đang convert: {v}")
                    ))

                    ok, result = convert_video_to_mp3(video_path, output_folder)

                    if ok:
                        success += 1
                        app.after(0, lambda v=video, r=result: append_log(f"✅ Xong: {v} -> {r}"))
                    else:
                        failed += 1
                        app.after(0, lambda v=video, r=result: append_log(f"❌ Lỗi: {v} -> {r}"))

                    app.after(0, lambda i=index, t=total: progress_bar.set(i / t))

                def done():
                    refresh_grid()
                    convert_btn.configure(state="normal", text="▶ Convert tất cả video sang MP3")
                    convert_status.configure(text=f"Convert xong: {success} thành công, {failed} lỗi")
                    progress_bar.set(1)
                    messagebox.showinfo("Convert xong", f"{success} thành công / {failed} lỗi")

                app.after(0, done)

            threading.Thread(target=worker, daemon=True).start()

        convert_btn = ctk.CTkButton(
            frame,
            text="▶ Convert tất cả video sang MP3",
            fg_color="#16a34a",
            hover_color="#15803d",
            command=convert_video_folder
        )
        convert_btn.pack(fill="x", padx=15, pady=12)

    def show_board_page():
        clear_page()
        show_back_title("📁 Quản lý bảng")

        create_frame = ctk.CTkFrame(page_container)
        create_frame.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(create_frame, text="Tạo bảng mới", font=("Arial", 16, "bold")).pack(pady=8)
        ctk.CTkEntry(create_frame, textvariable=board_name_var, placeholder_text="Nhập tên bảng mới").pack(fill="x", padx=15, pady=6)

        list_frame = ctk.CTkScrollableFrame(page_container)
        list_frame.pack(fill="both", expand=True, padx=20, pady=10)

        def refresh_board_list():
            for w in list_frame.winfo_children():
                w.destroy()

            for board in BOARDS:
                row = ctk.CTkFrame(list_frame)
                row.pack(fill="x", pady=5)

                label = ctk.CTkLabel(row, text=board["name"], anchor="w", font=("Arial", 15, "bold"))
                label.pack(side="left", fill="x", expand=True, padx=10, pady=8)

                def rename_board(b=board, r=row):
                    for c in r.winfo_children():
                        c.destroy()

                    var = ctk.StringVar(value=b["name"])
                    entry = ctk.CTkEntry(r, textvariable=var)
                    entry.pack(side="left", fill="x", expand=True, padx=10, pady=5)
                    entry.focus()

                    def save():
                        new_name = var.get().strip()
                        old_name = b["name"]
                        old_path = b["folder"]
                        new_path = os.path.join(SOUNDS_ROOT, new_name)

                        if not new_name or new_name == old_name:
                            refresh_board_list()
                            return

                        if os.path.exists(new_path):
                            messagebox.showwarning("Lỗi", "Tên bảng đã tồn tại")
                            refresh_board_list()
                            return

                        confirm = messagebox.askyesno("Xác nhận đổi tên", f"Bạn có chắc muốn đổi tên bảng:\n\n{old_name} → {new_name}?")
                        if not confirm:
                            refresh_board_list()
                            return

                        try:
                            os.rename(old_path, new_path)
                            reload_boards()

                            for i, item in enumerate(BOARDS):
                                if item["name"] == new_name:
                                    switch_board(i)
                                    break

                            refresh_board_list()
                        except Exception as e:
                            messagebox.showerror("Lỗi", f"Không đổi tên được bảng:\n{e}")
                            refresh_board_list()

                    def cancel():
                        refresh_board_list()

                    entry.bind("<Return>", lambda e: save())
                    entry.bind("<Escape>", lambda e: cancel())

                    ctk.CTkButton(r, text="Lưu", width=60, command=save).pack(side="right", padx=5)
                    ctk.CTkButton(r, text="Huỷ", width=60, command=cancel).pack(side="right", padx=5)

                def delete_board(b=board):
                    if len(BOARDS) <= 1:
                        messagebox.showwarning("Lỗi", "Không thể xoá bảng cuối cùng")
                        return

                    confirm = messagebox.askyesno(
                        "Xác nhận xoá bảng",
                        f"Bạn có chắc muốn xoá bảng '{b['name']}' không?\n\nBảng sẽ được chuyển vào thư mục deleted_boards để có thể khôi phục."
                    )

                    if not confirm:
                        return

                    try:
                        os.makedirs(DELETED_BOARDS_ROOT, exist_ok=True)
                        backup_path = os.path.join(DELETED_BOARDS_ROOT, b["name"])

                        count = 1
                        while os.path.exists(backup_path):
                            backup_path = os.path.join(DELETED_BOARDS_ROOT, f"{b['name']}_{count}")
                            count += 1

                        shutil.move(b["folder"], backup_path)
                        reload_boards()
                        refresh_board_list()
                    except Exception as e:
                        messagebox.showerror("Lỗi", f"Không xoá được bảng:\n{e}")

                ctk.CTkButton(row, text="✏️", width=45, command=lambda b=board, r=row: rename_board(b, r)).pack(side="right", padx=4)
                ctk.CTkButton(row, text="🗑", width=45, fg_color="#b91c1c", hover_color="#7f1d1d", command=lambda b=board: delete_board(b)).pack(side="right", padx=4)

        def create_new_folder_board():
            name = board_name_var.get().strip()

            if not name:
                messagebox.showwarning("Thiếu tên", "Chưa nhập tên bảng")
                return

            folder_path = os.path.join(SOUNDS_ROOT, name)

            if os.path.exists(folder_path):
                messagebox.showwarning("Lỗi", "Bảng đã tồn tại")
                return

            try:
                os.makedirs(folder_path, exist_ok=True)
                board_name_var.set("")

                reload_boards()

                for i, board in enumerate(BOARDS):
                    if board["name"] == name:
                        switch_board(i)
                        break

                refresh_board_list()
                messagebox.showinfo("Thành công", "Đã tạo bảng mới")
            except Exception as e:
                messagebox.showerror("Lỗi", f"Lỗi tạo bảng:\n{e}")

        def add_existing_folder_board():
            folder = filedialog.askdirectory(title="Chọn thư mục âm thanh")

            if not folder:
                return

            folder_name = os.path.basename(folder)
            new_path = os.path.join(SOUNDS_ROOT, folder_name)

            try:
                if not os.path.exists(new_path):
                    shutil.copytree(folder, new_path)

                reload_boards()

                for i, board in enumerate(BOARDS):
                    if board["name"] == folder_name:
                        switch_board(i)
                        break

                refresh_board_list()
                messagebox.showinfo("Thành công", "Đã thêm bảng từ thư mục")
            except Exception as e:
                messagebox.showerror("Lỗi", f"Lỗi thêm thư mục:\n{e}")

        ctk.CTkButton(create_frame, text="➕ Tạo bảng mới", command=create_new_folder_board).pack(fill="x", padx=15, pady=6)
        ctk.CTkButton(create_frame, text="📂 Thêm bảng từ thư mục có sẵn", command=add_existing_folder_board).pack(fill="x", padx=15, pady=6)
        ctk.CTkButton(create_frame, text="🔄 Load lại bảng", command=lambda: (reload_boards(), refresh_board_list())).pack(fill="x", padx=15, pady=6)

        ctk.CTkLabel(page_container, text="Danh sách bảng hiện có", font=("Arial", 15, "bold")).pack(pady=(8, 0))
        refresh_board_list()

    def show_grid_settings_page():
        global GRID_COLS, GRID_ROWS, MAX_SOUNDS

        clear_page()
        show_back_title("🔢 Tuỳ chỉnh hàng / cột")

        frame = ctk.CTkFrame(page_container)
        frame.pack(fill="x", padx=20, pady=20)

        ctk.CTkLabel(frame, text="Số cột", font=("Arial", 16, "bold")).pack(pady=8)
        col_box = ctk.CTkOptionMenu(
            frame,
            values=["3", "4", "5", "6", "7", "8"],
            variable=ctk.StringVar(value=str(GRID_COLS))
        )
        col_box.pack(fill="x", padx=20, pady=8)

        ctk.CTkLabel(frame, text="Số hàng", font=("Arial", 16, "bold")).pack(pady=8)
        row_box = ctk.CTkOptionMenu(
            frame,
            values=["2", "3", "4", "5", "6"],
            variable=ctk.StringVar(value=str(GRID_ROWS))
        )
        row_box.pack(fill="x", padx=20, pady=8)

        ctk.CTkLabel(
            frame,
            text="Tên âm thanh sẽ tự co chữ theo kích thước ô và tự thêm ... khi quá dài.",
            font=("Arial", 13),
            wraplength=400
        ).pack(pady=10)

        def apply_grid_settings():
            global GRID_COLS, GRID_ROWS, MAX_SOUNDS

            GRID_COLS = int(col_box.get())
            GRID_ROWS = int(row_box.get())
            MAX_SOUNDS = GRID_COLS * GRID_ROWS

            refresh_grid()
            save_settings()
            messagebox.showinfo("Đã lưu", f"Đã đổi bảng thành {GRID_ROWS} hàng x {GRID_COLS} cột")

        ctk.CTkButton(
            frame,
            text="💾 Lưu cấu hình",
            fg_color="#16a34a",
            hover_color="#15803d",
            command=apply_grid_settings
        ).pack(fill="x", padx=20, pady=20)

    show_main_menu()


# ================= MAIN UI =================

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

if DND_AVAILABLE:
    app = CTkDnD()
else:
    app = ctk.CTk()
app.title("Soundboard Livestream - Dev By Duy Trịnh")
app.geometry(SETTINGS.get("window_size", "660x540"))
app.minsize(520, 420)
app.resizable(True, True)

top_frame = ctk.CTkFrame(app, fg_color="transparent")
top_frame.pack(fill="x", padx=15, pady=(10, 4))

title = ctk.CTkLabel(
    top_frame,
    text="SOUND BOARD",
    font=("Arial", 22, "bold")
)
title.pack(side="left", padx=(0, 10))

btn_group = ctk.CTkFrame(top_frame, fg_color="transparent")
btn_group.pack(side="right")

pause_btn = ctk.CTkButton(
    btn_group,
    text="⏸ Pause",
    width=76,
    height=30,
    font=("Segoe UI", 12, "bold"),
    fg_color="#f59e0b",
    hover_color="#d97706",
    command=toggle_pause
)
pause_btn.pack(side="left", padx=3)

stop_btn = ctk.CTkButton(
    btn_group,
    text="⏹ Stop",
    width=66,
    height=30,
    font=("Segoe UI", 12, "bold"),
    fg_color="#b91c1c",
    hover_color="#7f1d1d",
    command=stop_sound
)
stop_btn.pack(side="left", padx=3)

reload_btn = ctk.CTkButton(
    btn_group,
    text="🔄",
    width=42,
    height=30,
    command=reload_current_board
)
reload_btn.pack(side="left", padx=3)

settings_btn = ctk.CTkButton(
    btn_group,
    text="⚙",
    width=42,
    height=30,
    command=open_settings
)
settings_btn.pack(side="left", padx=3)

board_btn_frame = ctk.CTkFrame(app)
board_btn_frame.pack(fill="x", padx=15, pady=5)

board_title = ctk.CTkLabel(app, text="", font=("Arial", 14))
board_title.pack(pady=5)

drop_hint = ctk.CTkLabel(
    app,
    text="Kéo thả mp3 hoặc mp4 vào đây để thêm vào bảng hiện tại" if DND_AVAILABLE else "Muốn kéo-thả: cài tkinterdnd2 bằng lệnh  python -m pip install tkinterdnd2",
    font=("Segoe UI", 11),
    text_color="#9ca3af"
)
drop_hint.pack(pady=(0, 3))

grid_frame = ctk.CTkFrame(app)
grid_frame.pack(fill="both", expand=True, padx=15, pady=10)
grid_frame.bind("<Configure>", lambda event: update_all_sound_button_texts())

enable_drag_drop(app)
enable_drag_drop(grid_frame)

volume_label = ctk.CTkLabel(app, text=f"Volume: {int(volume * 100)}%")
volume_label.pack()

slider = ctk.CTkSlider(app, from_=0, to=1, command=set_volume)
slider.set(volume)
slider.pack(fill="x", padx=30, pady=5)

refresh_board_buttons()

last_board = SETTINGS.get("last_board", 0)
if last_board >= len(BOARDS):
    last_board = 0

switch_board(last_board)

app.protocol("WM_DELETE_WINDOW", lambda: (save_settings(), app.destroy()))
app.mainloop()
