import csv
import os
import re
import random
from rich_stdout import Terminal, Colour, Effect

# Initialize Terminal Globally
term = Terminal()

class Song:
    max_playlist_name: int = 0
    playlist_names: dict[str, str] = {}
    
    def __init__(self, data: dict) -> None:
        self.title: str = data.get('Track Name', 'Unknown').strip()
        self.artist: str = data.get('Artist Name(s)', 'Unknown').strip()
        self.genre: str = data.get('Genres', 'Unknown').strip()
        self.playlist: str = data.get('Playlist', 'Unknown').strip()
        dur_int, dur_str = self._time_to_int_and_str(data['Duration (ms)'] or '0')
        self.duration_secs: int = dur_int
        self.duration_str: str = dur_str
        
        Song.update_longest_playlist_name(self.playlist)
        
    @staticmethod
    def _time_to_int_and_str(milliseconds: str) -> tuple[int, str]:
        seconds: int = int(milliseconds) // 1000
        
        parts: list[str] = []

        if seconds < 60:
            parts.append('0')
            parts.append(str(seconds))
        else:
            parts.append(str(seconds // 60))
            parts.append(str(seconds % 60))
            
        while len(parts[1]) < 2:
            parts[1] = f'0{parts[1]}'
            
        return (seconds, ':'.join(parts))
        
    @staticmethod
    def _time_to_seconds(time_str: str) -> int:
        try:
            parts = list(map(int, str(time_str).split(':')))
            if len(parts) == 2: return parts[0] * 60 + parts[1]
            elif len(parts) == 3: return parts[0] * 3600 + parts[1] * 60 + parts[2]
        except: return 0
        return 0
            
    @staticmethod
    def get_longest_playlist_name() -> int:
        return Song.max_playlist_name
    
    @staticmethod
    def update_longest_playlist_name(name: str) -> None:
        if len(name) > Song.get_longest_playlist_name():
            Song.max_playlist_name = len(name)

    def _match_text(self, text: str, query: str) -> bool:
        if query.startswith('/') and query.endswith('/') and len(query) > 2:
            pattern = query[1:-1]
            try:
                return bool(re.search(pattern, text, re.IGNORECASE))
            except re.error:
                return False
        return query.lower() in text.lower()

    def get_match_score(self, query: str) -> int:
        if not query: return 0
        clean_query = query.strip()
        
        # Global Search
        if clean_query.startswith('/') and clean_query.endswith('/'):
            full_text = f"{self.title} {self.artist} {self.genre} {self.playlist}"
            return 10 if self._match_text(full_text, clean_query) else 0

        # Field specific
        if clean_query.startswith('&'):
            return self._check_duration_match(clean_query[1:])
        if clean_query.startswith('@'):
            return 5 if self._match_text(self.artist, clean_query[1:]) else 0
        if clean_query.startswith('#'):
            return 5 if self._match_text(self.title, clean_query[1:]) else 0
        if clean_query.startswith('^'):
            return 5 if self._match_text(self.genre, clean_query[1:]) else 0
            
        return self._standard_score(clean_query)

    def _check_duration_match(self, query_time: str) -> int:
        try:
            if '+' in query_time:
                target_str, tolerance_str = query_time.split('+')
                tolerance = int(tolerance_str)
            else:
                target_str, tolerance = query_time, 0
            target_secs = self._time_to_seconds(target_str)
            if (target_secs - tolerance) <= self.duration_secs <= (target_secs + tolerance):
                diff = abs(target_secs - self.duration_secs)
                return 10 - diff if diff < 10 else 1
        except ValueError: pass
        return 0

    def _standard_score(self, term_val: str) -> int:
        total = 0
        if self._match_text(self.title, term_val): total += 3
        if self._match_text(self.artist, term_val): total += 3
        if self._match_text(self.genre, term_val): total += 2
        if self._match_text(self.playlist, term_val): total += 1
        return total

    def get_playlist_name(self) -> str:
        if self.playlist in Song.playlist_names:
            return Song.playlist_names[self.playlist]
        playlist_name = self.playlist.rjust(Song.get_longest_playlist_name() + 1)
        Song.playlist_names[self.playlist] = playlist_name
        return playlist_name

    def to_dict(self):
        return {'Song': self.title, 'Artist': self.artist, 'Genre': self.genre, 'Duration': self.duration_str, 'Playlist': self.playlist}

    def display(self):
        term.print(f"{self.get_playlist_name()}", effects=[Colour.FOREGROUND_PURPLE], new_line=True, reset_style=False)
        term.print(" / ", new_line=False, reset_style=True)
        term.print(f"{self.title}", effects=[Effect.BOLD, Colour.FOREGROUND_WHITE], new_line=False)
        term.print(f" - {self.artist} ", effects=[Colour.FOREGROUND_BLUE], new_line=False)
        term.print(f"[{self.genre}]", effects=[Colour.FOREGROUND_GREEN, Effect.FAINT], new_line=False)
        term.print(f" ({self.duration_str})", effects=[Colour.FOREGROUND_YELLOW], new_line=False)

def save_to_csv(songs: list[Song], path: str):
    if not songs:
        term.warning("No results to save.")
        return
    try:
        keys = ['Song', 'Artist', 'Genre', 'Duration', 'Playlist']
        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            for s in songs: writer.writerow(s.to_dict())
        term.success(f"Saved {len(songs)} songs to {path}")
    except Exception as e:
        term.error(f"Failed to save: {e}")

def load_csv_data(path: str) -> list[Song]:
    songs = []
    if os.path.isdir(path):
        for item in os.listdir(path):
            if item.endswith('.csv'): songs.extend(load_csv_data(os.path.join(path, item)))
    elif os.path.isfile(path) and path.endswith('.csv'):
        try:
            with open(path, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                p_name = os.path.basename(path).replace('.csv', '')
                for row in reader:
                    row['Playlist'] = p_name
                    songs.append(Song(row))
        except Exception as e: term.warning(f"Error reading {path}: {e}")
    return songs

def main_loop(library: list[Song]):
    last_results: list[Song] = []
    
    while True:
        term.print(
            "\nHINTS: @Artist, #Title, ^Genre, &Time+sec, /regex/ | (quit) :q, (save) :s <file>, (read) :o <path>, (random) :r <amount> , (clear) :c",
            effects=[Colour.FOREGROUND_YELLOW]
        )
        try:
            query = term.input("Search: ", effects=[Effect.BOLD]).strip()
        except KeyboardInterrupt: break

        if not query: continue

        if query.startswith(':'):
            parts = query.split(' ', 1)
            cmd, arg = parts[0].lower(), (parts[1] if len(parts) > 1 else "")
            if cmd == ':q': break
            elif cmd == ':s': save_to_csv(last_results, arg)
            elif cmd == ':o':
                new_data = load_csv_data(arg)
                library.extend(new_data)
                term.success(f"Added {len(new_data)} items.")
            elif cmd == ':c':
                term.clear()
                term.move_cursor(0, 0)
            elif cmd == ':r':
                arg = arg or '1'
                
                if not arg.isnumeric():
                    term.error(f'"{arg}" is not an integer')
                    continue
                for song in random.sample(library, int(arg)):
                    song.display()
            continue

        matches = sorted([ (s.get_match_score(query), s) for s in library if s.get_match_score(query) > 0 ], key=lambda x: x[0], reverse=True)
        last_results = [m[1] for m in matches]
        total = len(matches)

        if not matches:
            term.warning('No matches.')
            continue

        # Logic: Only page if results > 30
        if total <= 30:
            term.print(f"Results ({total}):", effects=[Effect.BOLD])
            for _, song in matches: song.display()
        else:
            page, p_size = 0, 20
            total_pages = (total + p_size - 1) // p_size
            while True:
                batch = matches[page * p_size : (page + 1) * p_size]
                term.print(f"Page {page+1}/{total_pages} ({total} matches):", effects=[Effect.BOLD])
                for _, song in batch: song.display()
                
                nav = term.input("Enter/n (Next), p (Prev), q (Quit View): ", effects=[Effect.FAINT], check=lambda x: True).lower().strip()
                if nav == 'q': break
                elif nav == 'p': page = max(0, page - 1)
                else:
                    if page < total_pages - 1: page += 1
                    else: break # End of results = quit view

if __name__ == "__main__":
    lib = load_csv_data('playlists/')
    term.success(f"Library: {len(lib)} songs.")
    main_loop(lib)