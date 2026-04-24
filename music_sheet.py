import json
import importlib
import threading
import time

try:
    _direct_input = importlib.import_module("pydirectinput")
except ImportError:
    _direct_input = None
except AttributeError:
    _direct_input = None

_auto_gui = None
_auto_gui_checked = False

from midi_convert import MIDI_NOTE_TO_MUSIC_NOTE, midi_to_custom_json


def _load_auto_gui():
    global _auto_gui_checked, _auto_gui
    if _auto_gui_checked:
        return _auto_gui

    try:
        _auto_gui = importlib.import_module("pyautogui")
    except ImportError:
        _auto_gui = None
    _auto_gui_checked = True
    return _auto_gui


def key_down(key):
    if _direct_input is not None:
        try:
            _direct_input.keyDown(key)
            return
        except Exception:
            pass

    auto_gui = _load_auto_gui()
    if auto_gui is not None:
        auto_gui.keyDown(key)
        return

    raise ImportError("Neither pydirectinput nor pyautogui is installed.")


def key_up(key):
    if _direct_input is not None:
        try:
            _direct_input.keyUp(key)
            return
        except Exception:
            pass

    auto_gui = _load_auto_gui()
    if auto_gui is not None:
        auto_gui.keyUp(key)
        return

    raise ImportError("Neither pydirectinput nor pyautogui is installed.")


class MusicTrack:
    def __init__(self, notes):
        self.notes = notes
    
    def play(self, note_to_key_mapping, stop_event=None):
        def sleep_with_stop(delay):
            if stop_event is None:
                time.sleep(delay)
                return False

            end_time = time.time() + delay
            while time.time() < end_time:
                if stop_event.is_set():
                    return True
                time.sleep(min(0.01, end_time - time.time()))
            return False

        for note, delay in self.notes:
            if stop_event and stop_event.is_set():
                return

            note = note.lower()
            key = note_to_key_mapping.get(note)
            if key:
                key_down(key)
                interrupted = sleep_with_stop(delay)
                key_up(key)
                if interrupted:
                    return
            elif note == "wait":
                interrupted = sleep_with_stop(delay)
                if interrupted:
                    return
            else:
                print(f"Warning: Note '{note}' not found in mapping. Skipping.")
                interrupted = sleep_with_stop(delay)
                if interrupted:
                    return


class MusicSheet:
    @staticmethod
    def _ticks_to_seconds_range(start_tick, duration_ticks, ticks_per_beat, tempo_events):
        if duration_ticks <= 0:
            return 0.0

        if not tempo_events:
            tempo_events = [{"tick": 0, "tempo": 500000}]

        ordered_events = sorted(tempo_events, key=lambda event: event.get("tick", 0))
        normalized_events = []
        for event in ordered_events:
            tick = int(event.get("tick", 0))
            tempo = int(event.get("tempo", 500000))
            if normalized_events and normalized_events[-1]["tick"] == tick:
                normalized_events[-1]["tempo"] = tempo
            else:
                normalized_events.append({"tick": tick, "tempo": tempo})

        if normalized_events[0]["tick"] > 0:
            normalized_events.insert(0, {"tick": 0, "tempo": 500000})

        range_start = int(start_tick)
        range_end = int(start_tick + duration_ticks)
        total_seconds = 0.0

        current_tempo = normalized_events[0]["tempo"]
        event_index = 1
        while event_index < len(normalized_events) and normalized_events[event_index]["tick"] <= range_start:
            current_tempo = normalized_events[event_index]["tempo"]
            event_index += 1

        segment_start = range_start
        while segment_start < range_end:
            next_change_tick = range_end
            if event_index < len(normalized_events):
                next_change_tick = min(next_change_tick, normalized_events[event_index]["tick"])

            segment_ticks = next_change_tick - segment_start
            if segment_ticks > 0:
                total_seconds += (segment_ticks / ticks_per_beat) * (current_tempo / 1_000_000)

            segment_start = next_change_tick
            if event_index < len(normalized_events) and segment_start == normalized_events[event_index]["tick"]:
                current_tempo = normalized_events[event_index]["tempo"]
                event_index += 1

        return total_seconds

    @classmethod
    def from_json(cls, file_path):
        if isinstance(file_path, str):
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        elif isinstance(file_path, dict):
            data = file_path
        else:
            raise ValueError("Input must be a file path or a JSON dictionary")
        
        version = data.get("version", "1.0")
        if version == "1.0":
            notes = [(note, delay) for note, delay in data["notes"]]
            return cls([MusicTrack(notes)])
        
        elif version == "2.0":
            midi_info = data.get("midi", {})
            delay_unit = data.get("delay_unit", "seconds")
            ticks_per_beat = int(midi_info.get("ticks_per_beat", 480))
            tempo_events = midi_info.get("tempo_events", [{"tick": 0, "tempo": 500000}])

            tracks = []
            for track_data in data["tracks"]:
                notes = []
                if delay_unit == "ticks":
                    track_tick_cursor = 0
                    for note, delay in track_data:
                        delay_ticks = int(delay)
                        delay_seconds = cls._ticks_to_seconds_range(
                            track_tick_cursor,
                            delay_ticks,
                            ticks_per_beat,
                            tempo_events,
                        )
                        notes.append((note, delay_seconds))
                        track_tick_cursor += delay_ticks
                else:
                    notes = [(note, float(delay)) for note, delay in track_data]

                tracks.append(MusicTrack(notes))
            return cls(tracks)
    
        elif version == "3.0":
            shift_note = data.get("shift_note", 0)

            notes = []
            for note, on_or_off, timestamp in data.get("notes", []):
                notes.append((note, on_or_off, float(timestamp)))
            return MusicSheetV3(notes, shift_note=shift_note)

    @classmethod
    def from_midi(cls, midi_path, shift_note=0):
        json_data = midi_to_custom_json(midi_path, shift_note=shift_note)
        return cls.from_json(json_data)

    def __init__(self, tracks: list[MusicTrack]):
        self.tracks: list[MusicTrack] = tracks
    
    def play(self, note_to_key_mapping, stop_event=None, timescale=1):
        threads = []
        for track in self.tracks:
            thread = threading.Thread(target=track.play, args=(note_to_key_mapping, stop_event), daemon=True)
            thread.start()
            threads.append(thread)
        
        for thread in threads:
            thread.join()


class MusicSheetV3:
    def __init__(self, notes, shift_note=0):
        self.notes = notes
        self.shift_note = shift_note
    
    def play(self, note_to_key_mapping, stop_event=None, timescale=1, shift_note=None):
        if shift_note is None:
            shift_note = self.shift_note

        current_time = 0
        
        last_time = time.time()
        for note, on_or_off, timestamp in self.notes:
            while current_time < timestamp:
                if stop_event and stop_event.is_set():
                    return

                now = time.time()
                current_time += (now - last_time) * timescale
                last_time = now
                if current_time >= timestamp:
                    break
                time.sleep(min(0.01, timestamp - current_time))
            
            def play_note(note, on_or_off):
                note = MIDI_NOTE_TO_MUSIC_NOTE.get(note + shift_note, f"unknown_{note + shift_note}").lower()
                key = note_to_key_mapping.get(note)
                if key:
                    if on_or_off == 1:
                        key_down(key)
                    else:
                        key_up(key)
                else:
                    print(f"Warning: Note '{note}' not found in mapping. Skipping.")

            t = threading.Thread(target=play_note, args=(note, on_or_off), daemon=True)
            t.start()
