import mido
import json


NOTES = ['c', 'c#', 'd', 'd#', 'e', 'f', 'f#', 'g', 'g#', 'a', 'a#', 'b']

# Generates mapping for the full MIDI range (0-127)
MIDI_NOTE_TO_MUSIC_NOTE = {
    i: f"{NOTES[i % 12]}{(i // 12) - 1}" 
    for i in range(0, 128)
}


def midi_get_note_range(midi_path):
    mid = mido.MidiFile(midi_path)
    merged_track = mido.merge_tracks(mid.tracks)

    min_note = 127
    max_note = 0

    for msg in merged_track:
        if msg.type == "note_on" and msg.velocity > 0:
            if msg.note < min_note:
                min_note = msg.note
            if msg.note > max_note:
                max_note = msg.note

    return min_note, max_note

def midi_to_custom_json(midi_path, output_path="output.json", shift_note=0):
    mid = mido.MidiFile(midi_path)
    
    draft_tracks = []
    current_note_pressed = {}
    
    def place_key_in_draft_tracks(note, start_time, end_time):
        for track in draft_tracks:
            can_place = True
            for _note, _start_time, _end_time in track:
                if (start_time < _end_time and end_time > _start_time):
                    # Overlap detected, place in next track
                    can_place = False
                    break
            
            if can_place:
                track.append((note, start_time, end_time))
                return

        draft_tracks.append([(note, start_time, end_time)])

    
    merged_track = mido.merge_tracks(mid.tracks)
    ticks_per_beat = mid.ticks_per_beat
    current_tempo = 500000  # Default MIDI tempo: 120 BPM

    current_tick = 0
    current_time_seconds = 0.0
    tempo_events = [{"tick": 0, "seconds": 0.0, "tempo": current_tempo, "bpm": mido.tempo2bpm(current_tempo)}]
    time_signature_events = []

    for msg in merged_track:
        delta_ticks = msg.time
        current_tick += delta_ticks
        current_time_seconds += mido.tick2second(delta_ticks, ticks_per_beat, current_tempo)

        # if msg.type == "time_signature":
        #     if "time_signature" not in print_status:
        #         print_status["time_signature"] = True
        #         print(msg.type, msg.time, msg.denominator, msg.clocks_per_click, msg.is_meta, msg.is_realtime, msg.notated_32nd_notes_per_beat, msg.numerator)
        #     pass
        # elif msg.type == "set_tempo":
        #     if "set_tempo" not in print_status:
        #         print_status["set_tempo"] = True
        #         print(msg.type, msg.time, msg.tempo, msg.is_meta, msg.is_realtime)
        #     pass
        # elif msg.type == "track_name":
        #     if "track_name" not in print_status:
        #         print_status["track_name"] = True
        #         print(msg.type, msg.time, msg.name, msg.is_meta, msg.is_realtime)
        # elif msg.type == "end_of_track":
        #     if "end_of_track" not in print_status:
        #         print_status["end_of_track"] = True
        #         print(msg.type, msg.time, msg.is_meta, msg.is_realtime)
        #     pass
        # elif msg.type == "program_change":
        #     if "program_change" not in print_status:
        #         print_status["program_change"] = True
        #         print(msg.channel, msg.program, msg.type, msg.time, msg.is_realtime)
        #     pass

        if msg.type == "set_tempo":
            current_tempo = msg.tempo
            tempo_events.append(
                {
                    "tick": current_tick,
                    "seconds": current_time_seconds,
                    "tempo": msg.tempo,
                    "bpm": mido.tempo2bpm(msg.tempo),
                }
            )
            continue

        if msg.type == "time_signature":
            time_signature_events.append(
                {
                    "tick": current_tick,
                    "seconds": current_time_seconds,
                    "numerator": msg.numerator,
                    "denominator": msg.denominator,
                    "clocks_per_click": msg.clocks_per_click,
                    "notated_32nd_notes_per_beat": msg.notated_32nd_notes_per_beat,
                }
            )
            continue

        if msg.type == "note_on" and msg.velocity > 0:
            note_key = (msg.channel, msg.note)
            # if "note_on" not in print_status:
            #     # print_status["note_on"] = True
            #     print(msg.type, msg.channel, msg.note, msg.time, msg.is_realtime, msg.velocity)
            if note_key in current_note_pressed:
                pass
            else:
                current_note_pressed[note_key] = current_time_seconds
            
            pass
        elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
            note_key = (msg.channel, msg.note)
            
            if note_key in current_note_pressed:
                start_time = current_note_pressed.pop(note_key)
                note = MIDI_NOTE_TO_MUSIC_NOTE.get(msg.note + shift_note, f"unknown_{msg.note + shift_note}")
                place_key_in_draft_tracks(note, start_time, current_time_seconds)

        else:
            # print(f"Unhandled message type: {msg.type} - {msg}")
            pass

    tracks = []
    for i, draft_track in enumerate(draft_tracks):
        draft_track.sort(key=lambda x: x[1])  # Sort by start_time

        last_time = 0
        track = []
        for note, start_time, end_time in draft_track:
            start_time = round(start_time, 6)
            end_time = round(end_time, 6)

            wait_after_previous_note = (start_time - last_time)
            if wait_after_previous_note > 0:
                track.append(("wait", round(wait_after_previous_note, 6)))

            duration = end_time - start_time
            if duration > 0:
                track.append((note, round(duration, 6)))

            last_time = end_time
        tracks.append(track)

    # print(len(tracks), tracks[0])
    with open(output_path, "w") as f:
        json.dump(
            {
                "version": "2.0",
                "midi": {
                    "ticks_per_beat": ticks_per_beat,
                    "tempo_events": tempo_events,
                    "time_signature_events": time_signature_events,
                },
                "tracks": tracks,
            },
            f,
            indent=4,
        )


def parse_args():
    import argparse
    parser = argparse.ArgumentParser(description="Convert MIDI file to custom JSON format")
    parser.add_argument("midi_file", help="Path to the MIDI file to convert")
    parser.add_argument("-o", "--output", default="output.json", help="Path to save the converted JSON file")
    parser.add_argument("--shift", type=int, default=0, help="Number of semitones to shift the notes (positive or negative)")
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    midi_to_custom_json(args.midi_file, output_path=args.output, shift_note=args.shift)
