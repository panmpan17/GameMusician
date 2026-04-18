import time
import pydirectinput
import json
import threading


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
                pydirectinput.keyDown(key)
                interrupted = sleep_with_stop(delay)
                pydirectinput.keyUp(key)
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
        with open(file_path, "r") as f:
            data = json.load(f)
        
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

    def __init__(self, tracks: list[MusicTrack]):
        self.tracks: list[MusicTrack] = tracks
    
    def play(self, note_to_key_mapping, stop_event=None):
        threads = []
        for track in self.tracks:
            thread = threading.Thread(target=track.play, args=(note_to_key_mapping, stop_event), daemon=True)
            thread.start()
            threads.append(thread)
        
        for thread in threads:
            thread.join()
            