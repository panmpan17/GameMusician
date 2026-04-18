import pydirectinput
import time
import json
import tkinter
import threading
import os

from midi_convert import midi_to_custom_json, midi_get_all_notes, MIDI_NOTE_TO_MUSIC_NOTE
from tkinter import filedialog, messagebox
from music_sheet import MusicSheet


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

        self.selected_keymap_path = preferred_keymap_path
        self.selected_sheet_path = os.path.join("sheets", "little_stars.json")
        self.selected_midi_path = ""
        self.selected_midi_all_notes = {}
        
        self.sheet_playing = False
        self.sheet_counting_down = 3
        self.midi_playing = False
        self.midi_counting_down = 3

        self.selected_keymap = load_note_key_mapping(self.selected_keymap_path)
        self.selected_sheet = MusicSheet.from_json(self.selected_sheet_path)
        
        self._init_keymap_section()

        content_row = tkinter.Frame(master)
        content_row.pack(fill=tkinter.X, padx=8)

        self._init_midi_section(content_row)
        self._init_playback_section(content_row)
    
    def _init_keymap_section(self):
        self.keymap_section_label = tkinter.Label(self.master, text=f"Key Mapping:\n{self.selected_keymap_path}")
        self.keymap_section_label.pack(pady=(8, 0))

        keymap_button = tkinter.Button(self.master, text="Choose Key Mapping", command=self.choose_keymap_file)
        keymap_button.pack(pady=(4, 20))
    
    def _init_midi_section(self, parent):
        midi_frame = tkinter.Frame(parent)
        midi_frame.pack(side=tkinter.LEFT, fill=tkinter.BOTH, expand=True, padx=(0, 8))

        midi_section_label = tkinter.Label(midi_frame, text="MIDI to JSON")
        midi_section_label.pack(anchor="w")

        midi_button = tkinter.Button(midi_frame, text="Choose MIDI File", command=self.choose_midi_file)
        midi_button.pack(anchor="w", pady=(4, 0))

        self.midi_label = tkinter.Label(midi_frame, text="MIDI: (none)")
        self.midi_label.pack(anchor="w", pady=(2, 0))

        shift_label = tkinter.Label(midi_frame, text="Note Shift:")
        shift_label.pack(anchor="w", pady=(6, 0))

        self.shift_var = tkinter.StringVar(value="0")
        self.shift_var.trace_add("write", lambda *args: self.update_music_note_range_label())
        shift_slider = tkinter.Scale(midi_frame, from_=-48, to=48, length=50, orient=tkinter.HORIZONTAL, variable=self.shift_var)
        shift_slider.pack(anchor="w", fill=tkinter.X, pady=(2, 0))

        self.music_note_range_label = tkinter.Label(midi_frame, text="", justify=tkinter.LEFT)
        self.music_note_range_label.pack(anchor="w", pady=(2, 8))

        convert_button = tkinter.Button(midi_frame, text="Convert MIDI to JSON", command=self.convert_midi_to_json)
        convert_button.pack(anchor="w", pady=(6, 0))
        
        self.play_midi_button = tkinter.Button(midi_frame, text="Play MIDI", command=self.start_midi_playback_thread)
        self.play_midi_button.pack(anchor="w", pady=(4, 0))
    
    def _init_playback_section(self, parent):
        sheet_frame = tkinter.Frame(parent)
        sheet_frame.pack(side=tkinter.LEFT, fill=tkinter.BOTH, expand=True, padx=(8, 0))

        self.label = tkinter.Label(sheet_frame, text="Select a music sheet to play:")
        self.label.pack(anchor="w")

        self.sheet_button = tkinter.Button(sheet_frame, text="Choose Sheet", command=self.choose_sheet_file)
        self.sheet_button.pack(anchor="w", pady=(4, 0))

        self.sheet_label = tkinter.Label(sheet_frame, text=f"Sheet:\n{self.selected_sheet_path}")
        self.sheet_label.pack(anchor="w", pady=(2, 0))

        separator = tkinter.Label(sheet_frame, text="-----------------------------")
        separator.pack(pady=8)

        self.playing_thread = None
        self.stop_event = threading.Event()

        self.play_button = tkinter.Button(sheet_frame, text="Play", command=self.start_playback_thread)
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
            self.selected_sheet_path = selected_file
            self.selected_sheet = MusicSheet.from_json(selected_file)
            self.sheet_label.config(text=f"Sheet: {os.path.relpath(selected_file)}")
            self.preferences["selected_sheet_path"] = selected_file
            self.save_preferences(self.preferences)

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
        
        else:
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
                self.play_midi_button.config(text=f"Playing in {self.midi_counting_down} (Click to Stop)")
            else:
                self.play_midi_button.config(text="Playing... (Click to Stop)")
            
            self.play_button.config(state=tkinter.DISABLED)
        else:
            self.play_midi_button.config(text="Play MIDI")
            self.play_button.config(state=tkinter.NORMAL)
        
        if self.sheet_playing:
            if self.sheet_counting_down > 0:
                self.play_button.config(text=f"Playing in {self.sheet_counting_down} (Click to Stop)")
            else:
                self.play_button.config(text="Playing... (Click to Stop)")

            self.play_midi_button.config(state=tkinter.DISABLED)
        else:
            self.play_button.config(text="Play")
            self.play_midi_button.config(state=tkinter.NORMAL)
    
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
            messagebox.showerror("Playback Failed", str(exc))
        
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
            messagebox.showerror("Playback Failed", str(exc))
        
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
