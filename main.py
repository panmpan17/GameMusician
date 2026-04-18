import pydirectinput
import time
import json

from dataclasses import dataclass

def load_note_key_mapping(file_path):
    with open(file_path, "r") as f:
        data = json.load(f)
        result = {note.lower(): key for note, key in data.items()}
        return result

def load_music_sheet(file_path):
    with open(file_path, "r") as f:
        data = json.load(f)
        return [(note, delay) for note, delay in data["notes"]]
            

HEARTTOPIA_MUSIC_NOTE_TO_KEY = load_note_key_mapping("keymaps/heartopia.json")

C3_TO_C6 = load_music_sheet("sheets/c3_to_c6.json")
LITTLE_STARS_NOTES = load_music_sheet("sheets/little_stars.json")


def play_music_notes(notes, note_to_key_mapping):
    for note, delay in notes:
        note = note.lower()
        key = note_to_key_mapping.get(note)
        if key:
            pydirectinput.keyDown(key)
            time.sleep(delay)
            pydirectinput.keyUp(key)
        else:
            print(f"Warning: Note '{note}' not found in mapping. Skipping.")

if __name__ == "__main__":
    time.sleep(2)
    try:
        play_music_notes(C3_TO_C6, HEARTTOPIA_MUSIC_NOTE_TO_KEY)
    except KeyboardInterrupt:
        print("Interrupted by user. Exiting...")
