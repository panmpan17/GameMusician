import pydirectinput
import time
import json
import tkinter
import threading
import os

from tkinter import filedialog

from dataclasses import dataclass


DEFAULT_KEYMAP_PATH = os.path.join("keymaps", "heartopia.json")


def load_note_key_mapping(file_path):
    with open(file_path, "r") as f:
        data = json.load(f)
        result = {note.lower(): key for note, key in data.items()}
        return result

class MusicTrack:
    def __init__(self, notes):
        self.notes = notes


class MusicSheet:
    @classmethod
    def from_json(cls, file_path):
        with open(file_path, "r") as f:
            data = json.load(f)
        
        version = data.get("version", "1.0")
        if version == "1.0":
            notes = [(note, delay) for note, delay in data["notes"]]
            return cls([MusicTrack(notes)])

    def __init__(self, tracks: list[MusicTrack]):
        self.tracks: list[MusicTrack] = tracks
    
    def play(self, note_to_key_mapping):
        for track in self.tracks:
            for note, delay in track.notes:
                note = note.lower()
                key = note_to_key_mapping.get(note)
                if key:
                    pydirectinput.keyDown(key)
                    time.sleep(delay)
                    pydirectinput.keyUp(key)
                else:
                    print(f"Warning: Note '{note}' not found in mapping. Skipping.")
            

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

        self.selected_keymap_path = preferred_keymap_path
        self.selected_sheet_path = os.path.join("sheets", "little_stars.json")

        self.selected_keymap = load_note_key_mapping(self.selected_keymap_path)
        self.selected_sheet = MusicSheet.from_json(self.selected_sheet_path)

        self.label = tkinter.Label(master, text="Select a music sheet to play:")
        self.label.pack()

        self.keymap_button = tkinter.Button(master, text="Choose Key Mapping", command=self.choose_keymap_file)
        self.keymap_button.pack()

        self.keymap_label = tkinter.Label(master, text=f"Keymap: {self.selected_keymap_path}")
        self.keymap_label.pack()

        self.sheet_button = tkinter.Button(master, text="Choose Sheet", command=self.choose_sheet_file)
        self.sheet_button.pack()

        self.sheet_label = tkinter.Label(master, text=f"Sheet: {self.selected_sheet_path}")
        self.sheet_label.pack()

        self.play_button = tkinter.Button(master, text="Play", command=self.start_playback_thread)
        self.play_button.pack()

    def choose_keymap_file(self):
        selected_file = filedialog.askopenfilename(
            title="Select key mapping JSON",
            initialdir=os.path.abspath("keymaps"),
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if selected_file:
            self.selected_keymap_path = selected_file
            self.selected_keymap = load_note_key_mapping(selected_file)
            self.keymap_label.config(text=f"Keymap: {selected_file}")
            self.preferences["selected_keymap_path"] = selected_file
            self.save_preferences(self.preferences)

    def choose_sheet_file(self):
        selected_file = filedialog.askopenfilename(
            title="Select sheet JSON",
            initialdir=os.path.abspath("sheets"),
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if selected_file:
            self.selected_sheet_path = selected_file
            self.selected_sheet = MusicSheet.from_json(selected_file)
            self.sheet_label.config(text=f"Sheet: {selected_file}")
            self.preferences["selected_sheet_path"] = selected_file
            self.save_preferences(self.preferences)

    def start_playback_thread(self):
        self.play_button.config(state=tkinter.DISABLED)
        thread = threading.Thread(target=self.play_with_countdown, daemon=True)
        thread.start()

    def play_with_countdown(self):
        for seconds_left in range(3, 0, -1):
            self.master.after(0, self.play_button.config, {"text": str(seconds_left)})
            time.sleep(1)

        self.master.after(0, self.play_button.config, {"text": "Playing..."})
        self.selected_sheet.play(self.selected_keymap)
        self.master.after(0, self.play_button.config, {"text": "Play", "state": tkinter.NORMAL})


def parse_args():
    import argparse

    parser = argparse.ArgumentParser(description="Music Player for Heartopia")
    
    mode_subparsers = parser.add_subparsers(dest="mode", required=True, help="Mode of operation")
    
    mode_subparsers.add_parser("gui", help="Launch the GUI interface")
    
    cli_parser = mode_subparsers.add_parser("cli", help="Run in command-line mode")
    cli_parser.add_argument("--keymap", type=str, help="Path to key mapping JSON file", default=DEFAULT_KEYMAP_PATH)
    cli_parser.add_argument("--sheet", type=str, help="Path to music sheet JSON file", default=os.path.join("sheets", "little_stars.json"))
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    
    if args.mode == "gui":
        root = tkinter.Tk()
        app = MusicPlayerGUI(root)
        root.mainloop()
    
    elif args.mode == "cli":
        note_to_key_mapping = load_note_key_mapping(args.keymap)
        sheet = MusicSheet.from_json(args.sheet)
        sheet.play(note_to_key_mapping)
