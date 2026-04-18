import mido
import json


NOTES = ['c', 'c#', 'd', 'd#', 'e', 'f', 'f#', 'g', 'g#', 'a', 'a#', 'b']

# Generates mapping for the full MIDI range (0-127)
MIDI_NOTE_TO_MUSIC_NOTE = {
    i: f"{NOTES[i % 12]}{(i // 12) - 1}" 
    for i in range(0, 128)
}

    
def midi_to_custom_json(midi_path):
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

    print_status = {}
    count = 0
    current_time = 0
    for msg in mid:
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

        if msg.type == "note_on":
            current_time += msg.time
            # if "note_on" not in print_status:
            #     # print_status["note_on"] = True
            #     print(msg.type, msg.channel, msg.note, msg.time, msg.is_realtime, msg.velocity)
            if msg.note in current_note_pressed:
                pass
            else:
                current_note_pressed[msg.note] = current_time
            
            pass
        elif msg.type == "note_off":
            current_time += msg.time
            
            if msg.note in current_note_pressed:
                start_time = current_note_pressed.pop(msg.note)
                note = MIDI_NOTE_TO_MUSIC_NOTE.get(msg.note, f"unknown_{msg.note}")
                place_key_in_draft_tracks(note, start_time, current_time)

        else:
            # print(f"Unhandled message type: {msg.type} - {msg}")
            pass
        
        
        # count += 1
        # if count >= 100:
        #     break

    tracks = []
    for i, draft_track in enumerate(draft_tracks):
        draft_track.sort(key=lambda x: x[1])  # Sort by start_time

        last_time = 0
        track = []
        for note, start_time, end_time in draft_track:
            start_time *= 10
            end_time *= 10

            time = (start_time - last_time)
            print(f"Track {i}: Note {note} - Start: {start_time:.2f}, End: {end_time:.2f}, Duration: {end_time - start_time:.2f}")
            track.append((note, time))
            last_time = end_time
        tracks.append(track)

    # print(len(tracks), tracks[0])
    with open("output.json", "w") as f:
        json.dump({"version": "2.0", "tracks": tracks}, f, indent=4)


midi_to_custom_json("midi/canon.mid")
# print(MIDI_NOTE_TO_MUSIC_NOTE)
