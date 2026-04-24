import time
import json
import tkinter
import threading
import os

from midi_convert import midi_to_custom_json, midi_get_all_notes, MIDI_NOTE_TO_MUSIC_NOTE
from tkinter import filedialog, messagebox, simpledialog, ttk
from music_sheet import MusicSheet, PlaybackController


DEFAULT_KEYMAP_PATH = os.path.join("keymaps", "heartopia_22_keys.json")

def load_note_key_mapping(file_path):
    with open(file_path, "r") as f:
        data = json.load(f)
        result = {note.lower(): key for note, key in data.items()}
        return result


class MusicPlayerGUI:
    PREFERENCES_FILE = "preferences.json"
    
    @classmethod
    def load_preferences(cls):
        if not os.path.exists(cls.PREFERENCES_FILE):
            return {}

        try:
            with open(cls.PREFERENCES_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}

    @classmethod
    def save_preferences(cls, preferences):
        with open(cls.PREFERENCES_FILE, "w") as f:
            json.dump(preferences, f, indent=2)
    
    def __init__(self, master):
        self.master = master
        master.title("Music Player")

        self.preferences = self.load_preferences()

        preferred_keymap_path = self.preferences.get("selected_keymap_path", DEFAULT_KEYMAP_PATH)
        if not os.path.exists(preferred_keymap_path):
            preferred_keymap_path = DEFAULT_KEYMAP_PATH

        default_sheet_path = os.path.join("sheets", "little_stars.json")
        preferred_sheet_path = self.preferences.get("selected_sheet_path", default_sheet_path)
        if not os.path.exists(preferred_sheet_path):
            preferred_sheet_path = default_sheet_path

        self.selected_keymap_path = preferred_keymap_path
        self.selected_sheet_path = preferred_sheet_path
        self.selected_midi_path = ""
        self.selected_midi_all_notes = {}
        self.playlists = self._load_playlists()
        
        self.sheet_playing = False
        self.sheet_counting_down = 3
        self.midi_playing = False
        self.midi_counting_down = 3
        self.playlist_playing = False

        self.playing_thread = None
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.playback_controller = PlaybackController(stop_event=self.stop_event, pause_event=self.pause_event)

        self.selected_keymap = load_note_key_mapping(self.selected_keymap_path)
        self.selected_sheet = MusicSheet.from_json(self.selected_sheet_path)
        
        self._init_keymap_section()
        self._init_tabs()
        self.update_button_state()

    def _init_tabs(self):
        self.notebook = ttk.Notebook(self.master)
        self.notebook.pack(fill=tkinter.BOTH, expand=True, padx=8, pady=(0, 8))

        self.midi_tab = tkinter.Frame(self.notebook)
        self.play_tab = tkinter.Frame(self.notebook)
        self.playlist_tab = tkinter.Frame(self.notebook)

        self.notebook.add(self.midi_tab, text="MIDI")
        self.notebook.add(self.play_tab, text="Play Song")
        self.notebook.add(self.playlist_tab, text="Playlist")

        self._init_midi_section(self.midi_tab)
        self._init_playback_section(self.play_tab)
        self._init_playlist_section(self.playlist_tab)
    
    def _init_keymap_section(self):
        self.keymap_section_label = tkinter.Label(self.master, text=f"Key Mapping:\n{self.selected_keymap_path}")
        self.keymap_section_label.pack(pady=(8, 0))

        keymap_button = tkinter.Button(self.master, text="Choose Key Mapping", command=self.choose_keymap_file)
        keymap_button.pack(pady=(4, 20))
    
    def _init_midi_section(self, parent):
        midi_frame = tkinter.Frame(parent)
        midi_frame.pack(fill=tkinter.BOTH, expand=True, padx=8, pady=8)

        midi_section_label = tkinter.Label(midi_frame, text="MIDI to JSON")
        midi_section_label.pack(anchor="w")

        midi_button = tkinter.Button(midi_frame, text="Choose MIDI File", command=self.choose_midi_file)
        midi_button.pack(anchor="w", pady=(4, 0))

        self.midi_label = tkinter.Label(midi_frame, text="MIDI: (none)")
        self.midi_label.pack(anchor="w", pady=(2, 0))

        shift_label = tkinter.Label(midi_frame, text="Note Shift:")
        shift_label.pack(anchor="w", pady=(6, 0))

        self.shift_var = tkinter.IntVar(value=0)
        self.shift_var.trace_add("write", lambda *args: self.update_music_note_range_label())
        shift_slider = tkinter.Scale(midi_frame, from_=-48, to=48, length=50, orient=tkinter.HORIZONTAL, variable=self.shift_var)
        shift_slider.pack(anchor="w", fill=tkinter.X, pady=(2, 0))

        self.music_note_range_label = tkinter.Label(midi_frame, text="", justify=tkinter.LEFT)
        self.music_note_range_label.pack(anchor="w", pady=(2, 8))

        convert_button = tkinter.Button(midi_frame, text="Convert MIDI to JSON", command=self.convert_midi_to_json)
        convert_button.pack(anchor="w", pady=(6, 0))
        
        self.play_midi_button = tkinter.Button(midi_frame, text="Play MIDI", command=self.start_midi_playback_thread)
        self.play_midi_button.pack(anchor="w", pady=(4, 0))

        self.pause_midi_button = tkinter.Button(midi_frame, text="Pause MIDI", command=self.toggle_midi_pause)
        self.pause_midi_button.pack(anchor="w", pady=(4, 0))
    
    def _init_playback_section(self, parent):
        sheet_frame = tkinter.Frame(parent)
        sheet_frame.pack(fill=tkinter.BOTH, expand=True, padx=8, pady=8)

        self.label = tkinter.Label(sheet_frame, text="Import and play a music sheet:")
        self.label.pack(anchor="w")

        self.sheet_button = tkinter.Button(sheet_frame, text="Choose Sheet", command=self.choose_sheet_file)
        self.sheet_button.pack(anchor="w", pady=(4, 0))

        self.sheet_label = tkinter.Label(sheet_frame, text=f"Sheet:\n{self.selected_sheet_path}")
        self.sheet_label.pack(anchor="w", pady=(2, 0))

        separator = tkinter.Label(sheet_frame, text="-----------------------------")
        separator.pack(pady=8)

        self.play_button = tkinter.Button(sheet_frame, text="Play", command=self.start_playback_thread)
        self.play_button.pack(anchor="w")

        self.pause_song_button = tkinter.Button(sheet_frame, text="Pause", command=self.toggle_song_pause)
        self.pause_song_button.pack(anchor="w", pady=(4, 0))

    def _init_playlist_section(self, parent):
        section = tkinter.Frame(parent)
        section.pack(fill=tkinter.BOTH, expand=True, padx=8, pady=8)

        left_frame = tkinter.Frame(section)
        left_frame.pack(side=tkinter.LEFT, fill=tkinter.BOTH, expand=True, padx=(0, 8))

        right_frame = tkinter.Frame(section)
        right_frame.pack(side=tkinter.LEFT, fill=tkinter.BOTH, expand=True, padx=(8, 0))

        tkinter.Label(left_frame, text="Playlists").pack(anchor="w")
        playlist_list_frame = tkinter.Frame(left_frame)
        playlist_list_frame.pack(fill=tkinter.BOTH, expand=True, pady=(4, 0))

        self.playlist_listbox = tkinter.Listbox(playlist_list_frame, exportselection=False)
        self.playlist_listbox.pack(side=tkinter.LEFT, fill=tkinter.BOTH, expand=True)
        self.playlist_listbox.bind("<<ListboxSelect>>", self.on_playlist_selected)

        playlist_scrollbar = tkinter.Scrollbar(playlist_list_frame, orient=tkinter.VERTICAL, command=self.playlist_listbox.yview)
        playlist_scrollbar.pack(side=tkinter.RIGHT, fill=tkinter.Y)
        self.playlist_listbox.config(yscrollcommand=playlist_scrollbar.set)

        playlist_buttons = tkinter.Frame(left_frame)
        playlist_buttons.pack(fill=tkinter.X, pady=(6, 0))
        tkinter.Button(playlist_buttons, text="Add", command=self.add_playlist).pack(side=tkinter.LEFT)
        tkinter.Button(playlist_buttons, text="Remove", command=self.remove_playlist).pack(side=tkinter.LEFT, padx=(4, 0))
        tkinter.Button(playlist_buttons, text="Up", command=lambda: self.move_playlist(-1)).pack(side=tkinter.LEFT, padx=(4, 0))
        tkinter.Button(playlist_buttons, text="Down", command=lambda: self.move_playlist(1)).pack(side=tkinter.LEFT, padx=(4, 0))

        tkinter.Label(right_frame, text="Songs").pack(anchor="w")
        song_list_frame = tkinter.Frame(right_frame)
        song_list_frame.pack(fill=tkinter.BOTH, expand=True, pady=(4, 0))

        self.song_listbox = tkinter.Listbox(song_list_frame, exportselection=False)
        self.song_listbox.pack(side=tkinter.LEFT, fill=tkinter.BOTH, expand=True)

        song_scrollbar = tkinter.Scrollbar(song_list_frame, orient=tkinter.VERTICAL, command=self.song_listbox.yview)
        song_scrollbar.pack(side=tkinter.RIGHT, fill=tkinter.Y)
        self.song_listbox.config(yscrollcommand=song_scrollbar.set)

        song_buttons = tkinter.Frame(right_frame)
        song_buttons.pack(fill=tkinter.X, pady=(6, 0))
        tkinter.Button(song_buttons, text="Add Song", command=self.add_song_to_playlist).pack(side=tkinter.LEFT)
        tkinter.Button(song_buttons, text="Remove Song", command=self.remove_song_from_playlist).pack(side=tkinter.LEFT, padx=(4, 0))
        tkinter.Button(song_buttons, text="Up", command=lambda: self.move_song(-1)).pack(side=tkinter.LEFT, padx=(4, 0))
        tkinter.Button(song_buttons, text="Down", command=lambda: self.move_song(1)).pack(side=tkinter.LEFT, padx=(4, 0))

        playlist_action_buttons = tkinter.Frame(right_frame)
        playlist_action_buttons.pack(fill=tkinter.X, pady=(8, 0))
        self.play_playlist_button = tkinter.Button(playlist_action_buttons, text="Play Playlist", command=self.start_playlist_playback_thread)
        self.play_playlist_button.pack(side=tkinter.LEFT)

        self.pause_playlist_button = tkinter.Button(playlist_action_buttons, text="Pause Playlist", command=self.toggle_playlist_pause)
        self.pause_playlist_button.pack(side=tkinter.LEFT, padx=(6, 0))

        self.current_playlist_song_var = tkinter.StringVar(value="Current Song: (none)")
        self.current_playlist_song_label = tkinter.Label(right_frame, textvariable=self.current_playlist_song_var, justify=tkinter.LEFT)
        self.current_playlist_song_label.pack(anchor="w", pady=(6, 0))

        self.refresh_playlist_listbox()

    def _load_playlists(self):
        playlists_data = self.preferences.get("playlists", [])
        if not isinstance(playlists_data, list):
            return []

        normalized_playlists = []
        for playlist in playlists_data:
            if not isinstance(playlist, dict):
                continue

            name = str(playlist.get("name", "")).strip()
            songs = playlist.get("songs", [])
            if not name or not isinstance(songs, list):
                continue

            normalized_playlists.append(
                {
                    "name": name,
                    "songs": [str(song) for song in songs],
                }
            )

        return normalized_playlists

    def _save_playlists(self):
        self.preferences["playlists"] = self.playlists
        self.save_preferences(self.preferences)

    @staticmethod
    def _display_path(path):
        try:
            return os.path.relpath(path)
        except ValueError:
            return path

    def _set_selected_sheet(self, selected_file):
        self.selected_sheet_path = selected_file
        self.selected_sheet = MusicSheet.from_json(selected_file)
        self.sheet_label.config(text=f"Sheet: {self._display_path(selected_file)}")
        self.preferences["selected_sheet_path"] = selected_file
        self.save_preferences(self.preferences)

    def _get_selected_playlist_index(self):
        selection = self.playlist_listbox.curselection()
        if not selection:
            return None
        return selection[0]

    def _get_selected_song_index(self):
        selection = self.song_listbox.curselection()
        if not selection:
            return None
        return selection[0]

    def refresh_playlist_listbox(self):
        self.playlist_listbox.delete(0, tkinter.END)
        for playlist in self.playlists:
            self.playlist_listbox.insert(tkinter.END, playlist["name"])

        if self.playlists:
            self.playlist_listbox.selection_set(0)
            self.on_playlist_selected()
        else:
            self.song_listbox.delete(0, tkinter.END)

    def refresh_song_listbox(self, playlist_index):
        self.song_listbox.delete(0, tkinter.END)
        if playlist_index is None or playlist_index >= len(self.playlists):
            return

        for song_path in self.playlists[playlist_index]["songs"]:
            self.song_listbox.insert(tkinter.END, self._display_path(song_path))

    def on_playlist_selected(self, _event=None):
        playlist_index = self._get_selected_playlist_index()
        self.refresh_song_listbox(playlist_index)

    def add_playlist(self):
        name = simpledialog.askstring("Add Playlist", "Playlist name:", parent=self.master)
        if not name:
            return

        clean_name = name.strip()
        if not clean_name:
            return

        if any(playlist["name"].lower() == clean_name.lower() for playlist in self.playlists):
            messagebox.showerror("Duplicate Playlist", "A playlist with this name already exists.")
            return

        self.playlists.append({"name": clean_name, "songs": []})
        self._save_playlists()
        self.refresh_playlist_listbox()
        last_index = len(self.playlists) - 1
        self.playlist_listbox.selection_clear(0, tkinter.END)
        self.playlist_listbox.selection_set(last_index)
        self.on_playlist_selected()

    def remove_playlist(self):
        playlist_index = self._get_selected_playlist_index()
        if playlist_index is None:
            return

        playlist_name = self.playlists[playlist_index]["name"]
        should_delete = messagebox.askyesno("Remove Playlist", f"Delete playlist '{playlist_name}'?")
        if not should_delete:
            return

        self.playlists.pop(playlist_index)
        self._save_playlists()
        self.refresh_playlist_listbox()

    def move_playlist(self, direction):
        playlist_index = self._get_selected_playlist_index()
        if playlist_index is None:
            return

        new_index = playlist_index + direction
        if new_index < 0 or new_index >= len(self.playlists):
            return

        self.playlists[playlist_index], self.playlists[new_index] = self.playlists[new_index], self.playlists[playlist_index]
        self._save_playlists()
        self.refresh_playlist_listbox()
        self.playlist_listbox.selection_clear(0, tkinter.END)
        self.playlist_listbox.selection_set(new_index)
        self.on_playlist_selected()

    def add_song_to_playlist(self):
        playlist_index = self._get_selected_playlist_index()
        if playlist_index is None:
            messagebox.showerror("No Playlist", "Please select a playlist first.")
            return

        selected_file = filedialog.askopenfilename(
            title="Select sheet JSON",
            initialdir=os.path.abspath("sheets"),
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not selected_file:
            return

        songs = self.playlists[playlist_index]["songs"]
        songs.append(selected_file)
        self._save_playlists()
        self.refresh_song_listbox(playlist_index)
        last_index = len(songs) - 1
        self.song_listbox.selection_clear(0, tkinter.END)
        self.song_listbox.selection_set(last_index)

    def remove_song_from_playlist(self):
        playlist_index = self._get_selected_playlist_index()
        if playlist_index is None:
            return

        song_index = self._get_selected_song_index()
        if song_index is None:
            return

        self.playlists[playlist_index]["songs"].pop(song_index)
        self._save_playlists()
        self.refresh_song_listbox(playlist_index)

    def move_song(self, direction):
        playlist_index = self._get_selected_playlist_index()
        if playlist_index is None:
            return

        song_index = self._get_selected_song_index()
        if song_index is None:
            return

        songs = self.playlists[playlist_index]["songs"]
        new_index = song_index + direction
        if new_index < 0 or new_index >= len(songs):
            return

        songs[song_index], songs[new_index] = songs[new_index], songs[song_index]
        self._save_playlists()
        self.refresh_song_listbox(playlist_index)
        self.song_listbox.selection_clear(0, tkinter.END)
        self.song_listbox.selection_set(new_index)

    def start_playlist_playback_thread(self):
        if self.playlist_playing:
            self.playlist_playing = False
            self._stop_playback()
            self._set_current_playlist_song_name("Current Song: (stopped)")
            self.update_button_state()
            return

        if self.midi_playing or self.sheet_playing:
            messagebox.showerror("Busy", "Please stop current playback first.")
            return

        playlist_index = self._get_selected_playlist_index()
        if playlist_index is None:
            messagebox.showerror("No Playlist", "Please select a playlist first.")
            return

        songs = self.playlists[playlist_index]["songs"]
        if not songs:
            messagebox.showerror("Empty Playlist", "The selected playlist has no songs.")
            return

        self.playing_thread = threading.Thread(target=self.play_selected_playlist, args=(playlist_index,), daemon=True)
        self.playing_thread.start()

    def play_selected_playlist(self, playlist_index):
        self.playlist_playing = True
        self.stop_event.clear()
        self.pause_event.clear()
        self.update_button_state()

        songs = list(self.playlists[playlist_index]["songs"])
        for song_index, song_path in enumerate(songs):
            if self.stop_event.is_set():
                break

            if not os.path.exists(song_path):
                continue

            self._set_current_playlist_song_name(f"Current Song: {self._display_path(song_path)}")

            try:
                sheet = MusicSheet.from_json(song_path)
                sheet.play(self.selected_keymap, stop_event=self.stop_event, pause_event=self.pause_event, playback_controller=self.playback_controller)
            except Exception as exc:
                print(exc)
                self.master.after(0, lambda error=exc: messagebox.showerror("Playback Failed", str(error)))

            if self.stop_event.is_set():
                break

            if song_index < len(songs) - 1:
                self._set_current_playlist_song_name("Current Song: Waiting 3 seconds...")
                if not self._wait_with_controls(3):
                    break

        if self.stop_event.is_set():
            self._set_current_playlist_song_name("Current Song: (stopped)")
        else:
            self._set_current_playlist_song_name("Current Song: (finished)")

        self.playlist_playing = False
        self.pause_event.clear()
        self.playback_controller.release_all_pressed_keys()
        self.update_button_state()

    def _set_current_playlist_song_name(self, text):
        self.master.after(0, lambda: self.current_playlist_song_var.set(text))

    def _stop_playback(self):
        self.stop_event.set()
        self.pause_event.clear()
        self.playback_controller.release_all_pressed_keys()

    def _toggle_pause(self):
        if self.pause_event.is_set():
            self.pause_event.clear()
        else:
            self.pause_event.set()
            self.playback_controller.release_all_pressed_keys()
        self.update_button_state()

    def toggle_midi_pause(self):
        if self.midi_playing:
            self._toggle_pause()

    def toggle_song_pause(self):
        if self.sheet_playing:
            self._toggle_pause()

    def toggle_playlist_pause(self):
        if self.playlist_playing:
            self._toggle_pause()

    def _wait_with_controls(self, seconds):
        remaining = float(seconds)
        last_time = time.time()

        while remaining > 0:
            if self.stop_event.is_set():
                return False

            if self.pause_event.is_set():
                self.playback_controller.release_all_pressed_keys()
                while self.pause_event.is_set():
                    if self.stop_event.is_set():
                        return False
                    time.sleep(0.05)
                last_time = time.time()
                continue

            now = time.time()
            remaining -= (now - last_time)
            last_time = now
            if remaining > 0:
                time.sleep(min(0.05, remaining))

        return True

    def choose_keymap_file(self):
        selected_file = filedialog.askopenfilename(
            title="Select key mapping JSON",
            initialdir=os.path.abspath("keymaps"),
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if selected_file:
            self.selected_keymap_path = selected_file
            self.selected_keymap = load_note_key_mapping(selected_file)
            self.keymap_section_label.config(text=f"Key Mapping: {selected_file}")
            self.preferences["selected_keymap_path"] = selected_file
            self.save_preferences(self.preferences)

    def choose_sheet_file(self):
        selected_file = filedialog.askopenfilename(
            title="Select sheet JSON",
            initialdir=os.path.abspath("sheets"),
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if selected_file:
            self._set_selected_sheet(selected_file)

    def choose_midi_file(self):
        selected_file = filedialog.askopenfilename(
            title="Select MIDI file",
            initialdir=os.path.abspath("midi"),
            filetypes=[("MIDI files", "*.mid *.midi"), ("All files", "*.*")],
        )
        if selected_file:
            self.selected_midi_path = selected_file
            self.midi_label.config(text=f"MIDI: {os.path.relpath(selected_file)}")

            # Update music note range label
            self.selected_midi_all_notes = midi_get_all_notes(selected_file)
            self.update_music_note_range_label()

    def update_music_note_range_label(self):
        all_notes = self.selected_midi_all_notes

        if not all_notes:
            self.music_note_range_label.config(text="Music Note Range:\n(none)")
            self.update_midi_preview()
            return
        
        shift_value = int(self.shift_var.get())

        sorted_notes = sorted(all_notes.keys())
        min_note = sorted_notes[0] + shift_value
        max_note = sorted_notes[-1] + shift_value

        info = "Music Note Range:\n"
        info += f"{MIDI_NOTE_TO_MUSIC_NOTE.get(min_note, 'Unknown')} - {MIDI_NOTE_TO_MUSIC_NOTE.get(max_note, 'Unknown')}"

        missing_info = ""
        total_missing = 0
        added_missing_header = False
        for note in sorted_notes:
            shifted_note = note + shift_value
            shifted_note_name = MIDI_NOTE_TO_MUSIC_NOTE.get(shifted_note, "Unknown")
            if shifted_note_name not in self.selected_keymap:
                if not added_missing_header:
                    missing_info += "\nMissing in Keymap:"
                    added_missing_header = True
                missing_info += f"\n  {shifted_note_name} (Count {all_notes[note]})"
                total_missing += all_notes[note]

        if total_missing > 0:
            info += f"\n\n{total_missing} notes missing in keymap"
            info += missing_info

        self.music_note_range_label.config(text=info)

    def update_midi_preview(self):
        return

    def convert_midi_to_json(self):
        if not self.selected_midi_path:
            messagebox.showerror("Missing MIDI File", "Please choose a MIDI file first.")
            return

        try:
            shift = int(self.shift_var.get())
        except ValueError:
            messagebox.showerror("Invalid Shift", "Note Shift must be an integer.")
            return

        midi_name = os.path.splitext(os.path.basename(self.selected_midi_path))[0]
        save_path = filedialog.asksaveasfilename(
            title="Save converted JSON",
            initialdir=os.path.abspath("sheets"),
            initialfile=f"{midi_name}.json",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )

        if not save_path:
            return

        try:
            with open(save_path, "w") as f:
                json.dump(midi_to_custom_json(self.selected_midi_path, shift_note=shift), f, indent=4)
            messagebox.showinfo("Success", f"Converted and saved to:\n{save_path}")
        except Exception as exc:
            messagebox.showerror("Conversion Failed", str(exc))
    
    def start_midi_playback_thread(self):
        if self.midi_playing:
            self.midi_playing = False
            self._stop_playback()
            self.update_button_state()
            return

        if self.sheet_playing or self.playlist_playing:
            messagebox.showerror("Busy", "Please stop current playback first.")
            return

        if not self.selected_midi_path:
            messagebox.showerror("Missing MIDI File", "Please choose a MIDI file first.")
            return

        self.playing_thread = threading.Thread(target=self.play_midi_with_countdown, daemon=True)
        self.playing_thread.start()

    def start_playback_thread(self):
        if self.sheet_playing:
            self.sheet_playing = False
            self._stop_playback()
            self.update_button_state()
            return

        if self.midi_playing or self.playlist_playing:
            messagebox.showerror("Busy", "Please stop current playback first.")
            return

        self.playing_thread = threading.Thread(target=self.play_with_countdown, daemon=True)
        self.playing_thread.start()
    
    def update_button_state(self):
        paused = self.pause_event.is_set()

        if self.midi_playing:
            if self.midi_counting_down > 0:
                self.play_midi_button.config(text=f"Playing in {self.midi_counting_down} (Click to Stop)")
            else:
                self.play_midi_button.config(text="Playing... (Click to Stop)")
            
            self.play_button.config(state=tkinter.DISABLED)
            self.pause_midi_button.config(state=tkinter.NORMAL, text="Resume MIDI" if paused else "Pause MIDI")
        else:
            self.play_midi_button.config(text="Play MIDI")
            self.pause_midi_button.config(state=tkinter.DISABLED, text="Pause MIDI")
            if not self.sheet_playing and not self.playlist_playing:
                self.play_button.config(state=tkinter.NORMAL)
        
        if self.sheet_playing:
            if self.sheet_counting_down > 0:
                self.play_button.config(text=f"Playing in {self.sheet_counting_down} (Click to Stop)")
            else:
                self.play_button.config(text="Playing... (Click to Stop)")

            self.play_midi_button.config(state=tkinter.DISABLED)
            self.pause_song_button.config(state=tkinter.NORMAL, text="Resume" if paused else "Pause")
        else:
            self.play_button.config(text="Play")
            self.pause_song_button.config(state=tkinter.DISABLED, text="Pause")
            if not self.midi_playing and not self.playlist_playing:
                self.play_midi_button.config(state=tkinter.NORMAL)

        if self.playlist_playing:
            self.play_playlist_button.config(text="Stop Playlist")
            self.play_midi_button.config(state=tkinter.DISABLED)
            self.play_button.config(state=tkinter.DISABLED)
            self.pause_playlist_button.config(state=tkinter.NORMAL, text="Resume Playlist" if paused else "Pause Playlist")
        else:
            self.play_playlist_button.config(text="Play Playlist")
            self.pause_playlist_button.config(state=tkinter.DISABLED, text="Pause Playlist")
    
    def play_midi_with_countdown(self):
        self.midi_playing = True
        self.stop_event.clear()
        self.pause_event.clear()

        self.midi_counting_down = 3
        self.update_button_state()
        
        for _ in range(3, 0, -1):
            if self.stop_event.is_set():
                self.midi_playing = False
                self.update_button_state()
                return

            if not self._wait_with_controls(1):
                self.midi_playing = False
                self.update_button_state()
                return
            self.midi_counting_down -= 1
            self.update_button_state()
    
        try:
            sheet = MusicSheet.from_midi(self.selected_midi_path)
            sheet.play(
                self.selected_keymap,
                stop_event=self.stop_event,
                pause_event=self.pause_event,
                shift_note=int(self.shift_var.get()),
                playback_controller=self.playback_controller,
            )
        except Exception as exc:
            print(exc)
            messagebox.showerror("Playback Failed", str(exc))
        
        self.midi_playing = False
        self.pause_event.clear()
        self.playback_controller.release_all_pressed_keys()
        self.update_button_state()

    def play_with_countdown(self):
        self.sheet_playing = True
        self.stop_event.clear()
        self.pause_event.clear()

        self.sheet_counting_down = 3
        self.update_button_state()
        
        for _ in range(3, 0, -1):
            if self.stop_event.is_set():
                self.sheet_playing = False
                self.update_button_state()
                return

            if not self._wait_with_controls(1):
                self.sheet_playing = False
                self.update_button_state()
                return
            self.sheet_counting_down -= 1
            self.update_button_state()
    
        try:
            self.selected_sheet.play(
                self.selected_keymap,
                stop_event=self.stop_event,
                pause_event=self.pause_event,
                playback_controller=self.playback_controller,
            )
        except Exception as exc:
            print(exc)
            messagebox.showerror("Playback Failed", str(exc))
        
        self.sheet_playing = False
        self.pause_event.clear()
        self.playback_controller.release_all_pressed_keys()
        self.update_button_state()


def parse_args():
    import argparse

    parser = argparse.ArgumentParser(description="Music Player for Heartopia")
    
    mode_subparsers = parser.add_subparsers(dest="mode", required=True, help="Mode of operation")
    
    mode_subparsers.add_parser("gui", help="Launch the GUI interface")
    
    cli_parser = mode_subparsers.add_parser("cli", help="Run in command-line mode")
    cli_parser.add_argument("--keymap", type=str, help="Path to key mapping JSON file", default=DEFAULT_KEYMAP_PATH)
    cli_parser.add_argument("--sheet", type=str, help="Path to music sheet JSON file", default=os.path.join("sheets", "little_stars.json"))
    cli_parser.add_argument("--speed", type=float, help="Playback speed multiplier (e.g., 1.0 for normal speed)", default=1.0)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    
    if args.mode == "gui":
        root = tkinter.Tk()
        app = MusicPlayerGUI(root)
        root.mainloop()
    
    elif args.mode == "cli":
        time.sleep(3)  # Countdown before starting
        note_to_key_mapping = load_note_key_mapping(args.keymap)
        sheet = MusicSheet.from_json(args.sheet)
        sheet.play(note_to_key_mapping, timescale=args.speed)
