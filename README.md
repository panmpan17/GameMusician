# GameMusician

GameMusician is a fun project for playing music inside video games.

It lets you map in-game instrument keys to music notes, load a music sheet, and play songs automatically.

## Features

- Map game instrument keys to note names
- Load music sheets from JSON files
- Play songs by sending key input to the game
- Use custom keymaps and custom sheets

## Project Structure

- `main.py` - Main script
- `keymaps/` - Key mapping files for different games/instruments
- `sheets/` - Music sheet files
- `requirements.txt` - Python dependencies
- `install.bat` - Install dependencies on Windows
- `run.bat` - Run the project on Windows

## Requirements

- Python 3.14+ (recommended, install.bat will install for you)

## Installation

### Windows

**Option 1: Use batch script**
```bat
install.bat
```

**Option 2: Manual install**
```bat
python3 -m venv env
env\Scripts\activate
pip install -r requirements.txt
```

### Mac & Linux

```bat
python3 -m venv env
source env/bin/activate
pip install -r requirements.txt
```


## Usage

### Windows

**Option 1: Use batch script**
```bat
run.bat
```

**Option 2: Manual Execute**
```bat
env\Scripts\activate
python main.py
```

## How It Works

1. Choose or create a keymap in `keymaps/`.
2. Choose or create a music sheet in `sheets/`.
3. Start the game and open the in-game instrument.
4. Run the script.
5. Let GameMusician play the notes using your mapped keys.
