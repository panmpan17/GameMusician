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


class PlaybackController:
    def __init__(self, stop_event=None, pause_event=None):
        self.stop_event = stop_event if stop_event is not None else threading.Event()
        self.pause_event = pause_event if pause_event is not None else threading.Event()
        self._pressed_keys = set()
        self._lock = threading.Lock()

    def is_stopped(self):
        return self.stop_event.is_set()

    def is_paused(self):
        return self.pause_event.is_set()

    def press_key(self, key):
        key_down(key)
        with self._lock:
            self._pressed_keys.add(key)

    def release_key(self, key):
        try:
            key_up(key)
        finally:
            with self._lock:
                self._pressed_keys.discard(key)

    def release_all_pressed_keys(self):
        with self._lock:
            keys_to_release = list(self._pressed_keys)

        for key in keys_to_release:
            try:
                key_up(key)
            except Exception:
                pass

        with self._lock:
            for key in keys_to_release:
                self._pressed_keys.discard(key)

        return keys_to_release

    def wait_while_paused(self):
        while self.is_paused():
            if self.is_stopped():
                return True
            time.sleep(0.01)
        return self.is_stopped()


class MusicTrack:
    def __init__(self, notes):
        self.notes = notes
    
    def play(self, note_to_key_mapping, stop_event=None, timescale=1, playback_controller=None):
        controller = playback_controller or PlaybackController(stop_event=stop_event)

        def sleep_with_control(delay, active_key=None):
            if delay <= 0:
                return controller.is_stopped()

            remaining = float(delay)
            last_time = time.time()

            while remaining > 0:
                if controller.is_stopped():
                    return True

                if controller.is_paused():
                    if active_key is not None:
                        controller.release_key(active_key)

                    if controller.wait_while_paused():
                        return True

                    if active_key is not None:
                        controller.press_key(active_key)
                    last_time = time.time()
                    continue

                now = time.time()
                elapsed = (now - last_time) * timescale
                last_time = now
                remaining -= elapsed
                if remaining > 0:
                    time.sleep(min(0.01, remaining / max(timescale, 0.001)))

            return False

        for note, delay in self.notes:
            if controller.is_stopped():
                return

            note = note.lower()
            key = note_to_key_mapping.get(note)
            if key:
                if controller.wait_while_paused():
                    return

                controller.press_key(key)
                interrupted = sleep_with_control(delay, active_key=key)
                controller.release_key(key)
                if interrupted:
                    return
            elif note == "wait":
                interrupted = sleep_with_control(delay)
                if interrupted:
                    return
            else:
                print(f"Warning: Note '{note}' not found in mapping. Skipping.")
                interrupted = sleep_with_control(delay)
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
            with open(file_path, "r") as f:
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
    
    def play(self, note_to_key_mapping, stop_event=None, timescale=1, pause_event=None, playback_controller=None):
        controller = playback_controller or PlaybackController(stop_event=stop_event, pause_event=pause_event)
        threads = []
        for track in self.tracks:
            thread = threading.Thread(
                target=track.play,
                args=(note_to_key_mapping, stop_event, timescale, controller),
                daemon=True,
            )
            thread.start()
            threads.append(thread)
        
        for thread in threads:
            thread.join()

        controller.release_all_pressed_keys()


class MusicSheetV3:
    def __init__(self, notes, shift_note=0):
        self.notes = notes
        self.shift_note = shift_note
    
    def play(self, note_to_key_mapping, stop_event=None, timescale=1, shift_note=None, pause_event=None, playback_controller=None):
        if shift_note is None:
            shift_note = self.shift_note

        controller = playback_controller or PlaybackController(stop_event=stop_event, pause_event=pause_event)

        current_time = 0
        last_time = time.time()
        held_keys = set()

        def wait_for_unpause_with_restore():
            keys_to_restore = list(held_keys)
            for key in keys_to_restore:
                controller.release_key(key)

            if controller.wait_while_paused():
                return True

            for key in keys_to_restore:
                if controller.is_stopped() or controller.is_paused():
                    break
                controller.press_key(key)
            return False

        for note, on_or_off, timestamp in self.notes:
            while current_time < timestamp:
                if controller.is_stopped():
                    controller.release_all_pressed_keys()
                    return

                if controller.is_paused():
                    if wait_for_unpause_with_restore():
                        controller.release_all_pressed_keys()
                        return
                    last_time = time.time()
                    continue

                now = time.time()
                current_time += (now - last_time) * timescale
                last_time = now
                if current_time >= timestamp:
                    break
                time.sleep(min(0.01, timestamp - current_time))

            while controller.is_paused():
                if wait_for_unpause_with_restore():
                    controller.release_all_pressed_keys()
                    return
                last_time = time.time()

            music_note = MIDI_NOTE_TO_MUSIC_NOTE.get(note + shift_note, f"unknown_{note + shift_note}").lower()
            key = note_to_key_mapping.get(music_note)
            if key:
                if on_or_off == 1:
                    controller.press_key(key)
                    held_keys.add(key)
                else:
                    controller.release_key(key)
                    held_keys.discard(key)
            else:
                print(f"Warning: Note '{music_note}' not found in mapping. Skipping.")

        controller.release_all_pressed_keys()
