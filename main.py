import time
import json
import tkinter
import threading
import os

from midi_convert import midi_to_custom_json, midi_get_all_notes, MIDI_NOTE_TO_MUSIC_NOTE
from tkinter import filedialog, messagebox, simpledialog, ttk
from music_sheet import MusicSheet


DEFAULT_KEYMAP_PATH = os.path.join("keymaps", "heartopia_22_keys.json")
DEFAULT_LANGUAGE = "english"
SUPPORTED_LANGUAGES = {
    "english": "English",
    "chinese": "中文",
}
LOCALES_DIR = "locals"

def load_note_key_mapping(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
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
            with open(cls.PREFERENCES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}

    @classmethod
    def save_preferences(cls, preferences):
        with open(cls.PREFERENCES_FILE, "w", encoding="utf-8") as f:
            json.dump(preferences, f, indent=2)

    @staticmethod
    def load_locale(language):
        locale_path = os.path.join(LOCALES_DIR, f"{language}.json")
        if not os.path.exists(locale_path):
            return {}

        try:
            with open(locale_path, "r", encoding="utf-8") as f:
                locale_data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}

        if not isinstance(locale_data, dict):
            return {}

        return {str(key): str(value) for key, value in locale_data.items()}

    def _get_locale(self, language):
        locale_data = self.locales.get(language, {})
        if locale_data:
            return locale_data
        return self.default_locale

    def t(self, key, language=None, **kwargs):
        locale_data = self.translations if language is None else self._get_locale(language)
        template = locale_data.get(key, self.default_locale.get(key, key))
        try:
            return template.format(**kwargs)
        except (KeyError, ValueError):
            return template

    @staticmethod
    def _language_display_name(language_code):
        return SUPPORTED_LANGUAGES.get(language_code, language_code)

    @staticmethod
    def _language_code_from_display_name(display_name):
        for code, label in SUPPORTED_LANGUAGES.items():
            if label == display_name:
                return code
        return DEFAULT_LANGUAGE
    
    def __init__(self, master):
        self.master = master

        self.preferences = self.load_preferences()
        preferred_language = str(self.preferences.get("preferred_language", DEFAULT_LANGUAGE)).lower()
        if preferred_language not in SUPPORTED_LANGUAGES:
            preferred_language = DEFAULT_LANGUAGE

        self.locales = {language: self.load_locale(language) for language in SUPPORTED_LANGUAGES}
        self.default_locale = self.locales.get(DEFAULT_LANGUAGE, {})
        self.current_language = preferred_language
        self.translations = self._get_locale(self.current_language)

        master.title(self.t("window_title"))

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

        self.selected_keymap = load_note_key_mapping(self.selected_keymap_path)
        self.selected_sheet = MusicSheet.from_json(self.selected_sheet_path)
        
        self._init_keymap_section()
        self._init_tabs()

    def _init_tabs(self):
        self.notebook = ttk.Notebook(self.master)
        self.notebook.pack(fill=tkinter.BOTH, expand=True, padx=8, pady=(0, 8))

        self.midi_tab = tkinter.Frame(self.notebook)
        self.play_tab = tkinter.Frame(self.notebook)
        self.playlist_tab = tkinter.Frame(self.notebook)

        self.notebook.add(self.midi_tab, text=self.t("tab_midi"))
        self.notebook.add(self.play_tab, text=self.t("tab_play_song"))
        self.notebook.add(self.playlist_tab, text=self.t("tab_playlist"))

        self._init_midi_section(self.midi_tab)
        self._init_playback_section(self.play_tab)
        self._init_playlist_section(self.playlist_tab)
    
    def _init_keymap_section(self):
        self.keymap_section_label = tkinter.Label(
            self.master,
            text=self.t("key_mapping_label", path=self._display_path(self.selected_keymap_path)),
        )
        self.keymap_section_label.pack(pady=(8, 0))

        keymap_button = tkinter.Button(self.master, text=self.t("choose_key_mapping_button"), command=self.choose_keymap_file)
        keymap_button.pack(pady=(4, 8))

        language_frame = tkinter.Frame(self.master)
        language_frame.pack(pady=(0, 14))

        self.language_label = tkinter.Label(language_frame, text=self.t("language_label"))
        self.language_label.pack(side=tkinter.LEFT)

        self.language_var = tkinter.StringVar(value=self._language_display_name(self.current_language))
        self.language_selector = ttk.Combobox(
            language_frame,
            textvariable=self.language_var,
            values=list(SUPPORTED_LANGUAGES.values()),
            state="readonly",
            width=10,
        )
        self.language_selector.bind("<<ComboboxSelected>>", self.on_language_selected)
        self.language_selector.pack(side=tkinter.LEFT, padx=(8, 0))

    def on_language_selected(self, _event=None):
        selected_display_name = self.language_var.get()
        selected_language = self._language_code_from_display_name(selected_display_name)

        if selected_language == self.current_language:
            return

        self.preferences["preferred_language"] = selected_language
        self.save_preferences(self.preferences)

        messagebox.showinfo(
            self.t("restart_required_title", language=selected_language),
            self.t("restart_required_message", language=selected_language),
        )
    
    def _init_midi_section(self, parent):
        midi_frame = tkinter.Frame(parent)
        midi_frame.pack(fill=tkinter.BOTH, expand=True, padx=8, pady=8)

        midi_section_label = tkinter.Label(midi_frame, text=self.t("midi_to_json_label"))
        midi_section_label.pack(anchor="w")

        midi_button = tkinter.Button(midi_frame, text=self.t("choose_midi_file_button"), command=self.choose_midi_file)
        midi_button.pack(anchor="w", pady=(4, 0))

        self.midi_label = tkinter.Label(midi_frame, text=self.t("midi_label_none"))
        self.midi_label.pack(anchor="w", pady=(2, 0))

        shift_label = tkinter.Label(midi_frame, text=self.t("note_shift_label"))
        shift_label.pack(anchor="w", pady=(6, 0))

        self.shift_var = tkinter.IntVar(value=0)
        self.shift_var.trace_add("write", lambda *args: self.update_music_note_range_label())
        shift_slider = tkinter.Scale(midi_frame, from_=-48, to=48, length=50, orient=tkinter.HORIZONTAL, variable=self.shift_var)
        shift_slider.pack(anchor="w", fill=tkinter.X, pady=(2, 0))

        self.music_note_range_label = tkinter.Label(midi_frame, text="", justify=tkinter.LEFT)
        self.music_note_range_label.pack(anchor="w", pady=(2, 8))

        convert_button = tkinter.Button(midi_frame, text=self.t("convert_midi_button"), command=self.convert_midi_to_json)
        convert_button.pack(anchor="w", pady=(6, 0))
        
        self.play_midi_button = tkinter.Button(midi_frame, text=self.t("play_midi_button"), command=self.start_midi_playback_thread)
        self.play_midi_button.pack(anchor="w", pady=(4, 0))
    
    def _init_playback_section(self, parent):
        sheet_frame = tkinter.Frame(parent)
        sheet_frame.pack(fill=tkinter.BOTH, expand=True, padx=8, pady=8)

        self.label = tkinter.Label(sheet_frame, text=self.t("import_and_play_label"))
        self.label.pack(anchor="w")

        self.sheet_button = tkinter.Button(sheet_frame, text=self.t("choose_sheet_button"), command=self.choose_sheet_file)
        self.sheet_button.pack(anchor="w", pady=(4, 0))

        self.sheet_label = tkinter.Label(sheet_frame, text=self.t("sheet_label", path=self._display_path(self.selected_sheet_path)))
        self.sheet_label.pack(anchor="w", pady=(2, 0))

        separator = tkinter.Label(sheet_frame, text="-----------------------------")
        separator.pack(pady=8)

        self.play_button = tkinter.Button(sheet_frame, text=self.t("play_button"), command=self.start_playback_thread)
        self.play_button.pack(anchor="w")

    def _init_playlist_section(self, parent):
        section = tkinter.Frame(parent)
        section.pack(fill=tkinter.BOTH, expand=True, padx=8, pady=8)

        left_frame = tkinter.Frame(section)
        left_frame.pack(side=tkinter.LEFT, fill=tkinter.BOTH, expand=True, padx=(0, 8))

        right_frame = tkinter.Frame(section)
        right_frame.pack(side=tkinter.LEFT, fill=tkinter.BOTH, expand=True, padx=(8, 0))

        tkinter.Label(left_frame, text=self.t("playlists_label")).pack(anchor="w")
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
        tkinter.Button(playlist_buttons, text=self.t("add_button"), command=self.add_playlist).pack(side=tkinter.LEFT)
        tkinter.Button(playlist_buttons, text=self.t("remove_button"), command=self.remove_playlist).pack(side=tkinter.LEFT, padx=(4, 0))
        tkinter.Button(playlist_buttons, text=self.t("up_button"), command=lambda: self.move_playlist(-1)).pack(side=tkinter.LEFT, padx=(4, 0))
        tkinter.Button(playlist_buttons, text=self.t("down_button"), command=lambda: self.move_playlist(1)).pack(side=tkinter.LEFT, padx=(4, 0))

        tkinter.Label(right_frame, text=self.t("songs_label")).pack(anchor="w")
        song_list_frame = tkinter.Frame(right_frame)
        song_list_frame.pack(fill=tkinter.BOTH, expand=True, pady=(4, 0))

        self.song_listbox = tkinter.Listbox(song_list_frame, exportselection=False)
        self.song_listbox.pack(side=tkinter.LEFT, fill=tkinter.BOTH, expand=True)

        song_scrollbar = tkinter.Scrollbar(song_list_frame, orient=tkinter.VERTICAL, command=self.song_listbox.yview)
        song_scrollbar.pack(side=tkinter.RIGHT, fill=tkinter.Y)
        self.song_listbox.config(yscrollcommand=song_scrollbar.set)

        song_buttons = tkinter.Frame(right_frame)
        song_buttons.pack(fill=tkinter.X, pady=(6, 0))
        tkinter.Button(song_buttons, text=self.t("add_song_button"), command=self.add_song_to_playlist).pack(side=tkinter.LEFT)
        tkinter.Button(song_buttons, text=self.t("remove_song_button"), command=self.remove_song_from_playlist).pack(side=tkinter.LEFT, padx=(4, 0))
        tkinter.Button(song_buttons, text=self.t("up_button"), command=lambda: self.move_song(-1)).pack(side=tkinter.LEFT, padx=(4, 0))
        tkinter.Button(song_buttons, text=self.t("down_button"), command=lambda: self.move_song(1)).pack(side=tkinter.LEFT, padx=(4, 0))

        playlist_action_buttons = tkinter.Frame(right_frame)
        playlist_action_buttons.pack(fill=tkinter.X, pady=(8, 0))
        self.play_playlist_button = tkinter.Button(playlist_action_buttons, text=self.t("play_playlist_button"), command=self.start_playlist_playback_thread)
        self.play_playlist_button.pack(side=tkinter.LEFT)

        self.current_playlist_song_var = tkinter.StringVar(value=self.t("current_song_none"))
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
        self.sheet_label.config(text=self.t("sheet_label", path=self._display_path(selected_file)))
        self.preferences["selected_sheet_path"] = selected_file
        self.save_preferences(self.preferences)

    def _json_filetypes(self):
        return [
            (self.t("filetype_json"), "*.json"),
            (self.t("filetype_all"), "*.*"),
        ]

    def _midi_filetypes(self):
        return [
            (self.t("filetype_midi"), "*.mid *.midi"),
            (self.t("filetype_all"), "*.*"),
        ]

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
        name = simpledialog.askstring(self.t("add_playlist_title"), self.t("playlist_name_prompt"), parent=self.master)
        if not name:
            return

        clean_name = name.strip()
        if not clean_name:
            return

        if any(playlist["name"].lower() == clean_name.lower() for playlist in self.playlists):
            messagebox.showerror(self.t("duplicate_playlist_title"), self.t("duplicate_playlist_message"))
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
        should_delete = messagebox.askyesno(
            self.t("remove_playlist_title"),
            self.t("remove_playlist_confirm", playlist_name=playlist_name),
        )
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
            messagebox.showerror(self.t("no_playlist_title"), self.t("no_playlist_message"))
            return

        selected_file = filedialog.askopenfilename(
            title=self.t("select_sheet_json_title"),
            initialdir=os.path.abspath("sheets"),
            filetypes=self._json_filetypes(),
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
            self.stop_event.set()
            self._set_current_playlist_song_name(self.t("current_song_stopped"))
            self.update_button_state()
            return

        if self.midi_playing or self.sheet_playing:
            messagebox.showerror(self.t("busy_title"), self.t("busy_message"))
            return

        playlist_index = self._get_selected_playlist_index()
        if playlist_index is None:
            messagebox.showerror(self.t("no_playlist_title"), self.t("no_playlist_message"))
            return

        songs = self.playlists[playlist_index]["songs"]
        if not songs:
            messagebox.showerror(self.t("empty_playlist_title"), self.t("empty_playlist_message"))
            return

        self.playing_thread = threading.Thread(target=self.play_selected_playlist, args=(playlist_index,), daemon=True)
        self.playing_thread.start()

    def play_selected_playlist(self, playlist_index):
        self.playlist_playing = True
        self.stop_event.clear()
        self.update_button_state()

        songs = list(self.playlists[playlist_index]["songs"])
        for song_index, song_path in enumerate(songs):
            if self.stop_event.is_set():
                break

            if not os.path.exists(song_path):
                continue

            self._set_current_playlist_song_name(self.t("current_song_path", path=self._display_path(song_path)))

            try:
                sheet = MusicSheet.from_json(song_path)
                sheet.play(self.selected_keymap, self.stop_event)
            except Exception as exc:
                print(exc)
                self.master.after(0, lambda error=exc: messagebox.showerror(self.t("playback_failed_title"), str(error)))

            if self.stop_event.is_set():
                break

            if song_index < len(songs) - 1:
                for _ in range(30):
                    if self.stop_event.is_set():
                        break
                    time.sleep(0.1)
                self._set_current_playlist_song_name(self.t("current_song_waiting"))

        if self.stop_event.is_set():
            self._set_current_playlist_song_name(self.t("current_song_stopped"))
        else:
            self._set_current_playlist_song_name(self.t("current_song_finished"))

        self.playlist_playing = False
        self.update_button_state()

    def _set_current_playlist_song_name(self, text):
        self.master.after(0, lambda: self.current_playlist_song_var.set(text))

    def choose_keymap_file(self):
        selected_file = filedialog.askopenfilename(
            title=self.t("select_key_mapping_json_title"),
            initialdir=os.path.abspath("keymaps"),
            filetypes=self._json_filetypes(),
        )
        if selected_file:
            self.selected_keymap_path = selected_file
            self.selected_keymap = load_note_key_mapping(selected_file)
            self.keymap_section_label.config(text=self.t("key_mapping_label", path=self._display_path(selected_file)))
            self.preferences["selected_keymap_path"] = selected_file
            self.save_preferences(self.preferences)

    def choose_sheet_file(self):
        selected_file = filedialog.askopenfilename(
            title=self.t("select_sheet_json_title"),
            initialdir=os.path.abspath("sheets"),
            filetypes=self._json_filetypes(),
        )
        if selected_file:
            self._set_selected_sheet(selected_file)

    def choose_midi_file(self):
        selected_file = filedialog.askopenfilename(
            title=self.t("select_midi_file_title"),
            initialdir=os.path.abspath("midi"),
            filetypes=self._midi_filetypes(),
        )
        if selected_file:
            self.selected_midi_path = selected_file
            self.midi_label.config(text=self.t("midi_label_path", path=os.path.relpath(selected_file)))

            # Update music note range label
            self.selected_midi_all_notes = midi_get_all_notes(selected_file)
            self.update_music_note_range_label()

    def update_music_note_range_label(self):
        all_notes = self.selected_midi_all_notes

        if not all_notes:
            self.music_note_range_label.config(text=self.t("music_note_range_none"))
            self.update_midi_preview()
            return
        
        shift_value = int(self.shift_var.get())

        sorted_notes = sorted(all_notes.keys())
        min_note = sorted_notes[0] + shift_value
        max_note = sorted_notes[-1] + shift_value

        info = self.t(
            "music_note_range_value",
            min_note=MIDI_NOTE_TO_MUSIC_NOTE.get(min_note, self.t("unknown_note")),
            max_note=MIDI_NOTE_TO_MUSIC_NOTE.get(max_note, self.t("unknown_note")),
        )

        missing_info = ""
        total_missing = 0
        added_missing_header = False
        for note in sorted_notes:
            shifted_note = note + shift_value
            shifted_note_name = MIDI_NOTE_TO_MUSIC_NOTE.get(shifted_note, self.t("unknown_note"))
            if shifted_note_name not in self.selected_keymap:
                if not added_missing_header:
                    missing_info += f"\n{self.t('missing_in_keymap_header')}"
                    added_missing_header = True
                missing_info += f"\n{self.t('missing_in_keymap_item', note=shifted_note_name, count=all_notes[note])}"
                total_missing += all_notes[note]

        if total_missing > 0:
            info += f"\n\n{self.t('missing_notes_total', count=total_missing)}"
            info += missing_info

        self.music_note_range_label.config(text=info)

    def update_midi_preview(self):
        return

    def convert_midi_to_json(self):
        if not self.selected_midi_path:
            messagebox.showerror(self.t("missing_midi_file_title"), self.t("missing_midi_file_message"))
            return

        try:
            shift = int(self.shift_var.get())
        except ValueError:
            messagebox.showerror(self.t("invalid_shift_title"), self.t("invalid_shift_message"))
            return

        midi_name = os.path.splitext(os.path.basename(self.selected_midi_path))[0]
        save_path = filedialog.asksaveasfilename(
            title=self.t("save_converted_json_title"),
            initialdir=os.path.abspath("sheets"),
            initialfile=f"{midi_name}.json",
            defaultextension=".json",
            filetypes=self._json_filetypes(),
        )

        if not save_path:
            return

        try:
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(midi_to_custom_json(self.selected_midi_path, shift_note=shift), f, indent=4)
            messagebox.showinfo(self.t("success_title"), self.t("converted_and_saved_message", path=save_path))
        except Exception as exc:
            messagebox.showerror(self.t("conversion_failed_title"), str(exc))
    
    def start_midi_playback_thread(self):
        if self.midi_playing:
            self.midi_playing = False
            self.stop_event.set()
            self.update_button_state()
            return

        self.playing_thread = threading.Thread(target=self.play_midi_with_countdown, daemon=True)
        self.playing_thread.start()

    def start_playback_thread(self):
        if self.sheet_playing:
            self.sheet_playing = False
            self.stop_event.set()
            self.update_button_state()
            return

        self.playing_thread = threading.Thread(target=self.play_with_countdown, daemon=True)
        self.playing_thread.start()
    
    def update_button_state(self):
        if self.midi_playing:
            if self.midi_counting_down > 0:
                self.play_midi_button.config(text=self.t("playing_in_stop", count=self.midi_counting_down))
            else:
                self.play_midi_button.config(text=self.t("playing_stop"))
            
            self.play_button.config(state=tkinter.DISABLED)
        else:
            self.play_midi_button.config(text=self.t("play_midi_button"))
            if not self.sheet_playing and not self.playlist_playing:
                self.play_button.config(state=tkinter.NORMAL)
        
        if self.sheet_playing:
            if self.sheet_counting_down > 0:
                self.play_button.config(text=self.t("playing_in_stop", count=self.sheet_counting_down))
            else:
                self.play_button.config(text=self.t("playing_stop"))

            self.play_midi_button.config(state=tkinter.DISABLED)
        else:
            self.play_button.config(text=self.t("play_button"))
            if not self.midi_playing and not self.playlist_playing:
                self.play_midi_button.config(state=tkinter.NORMAL)

        if self.playlist_playing:
            self.play_playlist_button.config(text=self.t("stop_playlist_button"))
            self.play_midi_button.config(state=tkinter.DISABLED)
            self.play_button.config(state=tkinter.DISABLED)
        else:
            self.play_playlist_button.config(text=self.t("play_playlist_button"))
    
    def play_midi_with_countdown(self):
        self.midi_playing = True
        self.stop_event.clear()

        self.midi_counting_down = 3
        self.update_button_state()
        
        for _ in range(3, 0, -1):
            if self.stop_event.is_set():
                self.midi_playing = False
                self.update_button_state()
                return
            
            time.sleep(1)
            self.midi_counting_down -= 1
            self.update_button_state()
    
        try:
            sheet = MusicSheet.from_midi(self.selected_midi_path)
            sheet.play(self.selected_keymap, self.stop_event, shift_note=int(self.shift_var.get()))
        except Exception as exc:
            print(exc)
            messagebox.showerror(self.t("playback_failed_title"), str(exc))
        
        self.midi_playing = False
        self.update_button_state()

    def play_with_countdown(self):
        self.sheet_playing = True
        self.stop_event.clear()

        self.sheet_counting_down = 3
        self.update_button_state()
        
        for _ in range(3, 0, -1):
            if self.stop_event.is_set():
                self.sheet_playing = False
                self.update_button_state()
                return
            
            time.sleep(1)
            self.sheet_counting_down -= 1
            self.update_button_state()
    
        try:
            self.selected_sheet.play(self.selected_keymap, self.stop_event)
        except Exception as exc:
            print(exc)
            messagebox.showerror(self.t("playback_failed_title"), str(exc))
        
        self.sheet_playing = False
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
