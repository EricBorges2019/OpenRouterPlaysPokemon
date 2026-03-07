from dataclasses import dataclass
from enum import IntEnum, IntFlag

from agent.constants import (
    Badge,
    ITEM_NAMES,
    MapLocation,
    Move,
    Pokemon,
    PokemonType,
    StatusCondition,
    Tileset,
)


@dataclass
class PokemonData:

    """Complete Pokemon data structure"""

    species_id: int
    species_name: str
    current_hp: int
    max_hp: int
    level: int
    status: StatusCondition
    type1: PokemonType
    type2: PokemonType | None
    moves: list[str]  # Move names
    move_pp: list[int]  # PP for each move
    trainer_id: int
    nickname: str | None = None
    experience: int | None = None
    
    @property
    def is_asleep(self) -> bool:
        """Check if the Pokémon is asleep"""
        return self.status.is_asleep
        
    @property
    def status_name(self) -> str:
        """Return a human-readable status name"""
        if self.is_asleep:
            return "SLEEP"
        elif self.status & StatusCondition.PARALYSIS:
            return "PARALYSIS"
        elif self.status & StatusCondition.FREEZE:
            return "FREEZE"
        elif self.status & StatusCondition.BURN:
            return "BURN"
        elif self.status & StatusCondition.POISON:
            return "POISON"
        else:
            return "OK"


class PokemonRedReader:
    """Reads and interprets memory values from Pokemon Red"""

    def __init__(self, memory_view):
        """Initialize with a PyBoy memory view object"""
        self.memory = memory_view

    def read_money(self) -> int:
        """Read the player's money in Binary Coded Decimal format"""
        b1 = self.memory[0xD349]  # Least significant byte
        b2 = self.memory[0xD348]  # Middle byte
        b3 = self.memory[0xD347]  # Most significant byte
        money = (
            ((b3 >> 4) * 100000)
            + ((b3 & 0xF) * 10000)
            + ((b2 >> 4) * 1000)
            + ((b2 & 0xF) * 100)
            + ((b1 >> 4) * 10)
            + (b1 & 0xF)
        )
        return money

    def _convert_text(self, bytes_data: list[int]) -> str:
        """Convert Pokemon text format to ASCII"""
        result = ""
        for b in bytes_data:
            if b == 0x50:  # End marker
                break
            elif b == 0x4E:  # Line break
                result += "\n"
            # Main character ranges
            elif 0x80 <= b <= 0x99:  # A-Z
                result += chr(b - 0x80 + ord("A"))
            elif 0xA0 <= b <= 0xB9:  # a-z
                result += chr(b - 0xA0 + ord("a"))
            elif 0xF6 <= b <= 0xFF:  # Numbers 0-9
                result += str(b - 0xF6)
            # Punctuation characters (9A-9F)
            elif b == 0x9A:  # (
                result += "("
            elif b == 0x9B:  # )
                result += ")"
            elif b == 0x9C:  # :
                result += ":"
            elif b == 0x9D:  # ;
                result += ";"
            elif b == 0x9E:  # [
                result += "["
            elif b == 0x9F:  # ]
                result += "]"
            # Special characters
            elif b == 0x7F:  # Space
                result += " "
            elif b == 0x6D:  # : (also appears here)
                result += ":"
            elif b == 0x54:  # POKé control character
                result += "POKé"
            elif b == 0xBA:  # é
                result += "é"
            elif b == 0xBB:  # 'd
                result += "'d"
            elif b == 0xBC:  # 'l
                result += "'l"
            elif b == 0xBD:  # 's
                result += "'s"
            elif b == 0xBE:  # 't
                result += "'t"
            elif b == 0xBF:  # 'v
                result += "'v"
            elif b == 0xE1:  # PK
                result += "Pk"
            elif b == 0xE2:  # MN
                result += "Mn"
            elif b == 0xE3:  # -
                result += "-"
            elif b == 0xE6:  # ?
                result += "?"
            elif b == 0xE7:  # !
                result += "!"
            elif b == 0xE8:  # .
                result += "."
            elif b == 0xE9:  # .
                result += "."
            # E-register special characters
            elif b == 0xE0:  # '
                result += "'"
            elif b == 0xE1:  # PK
                result += "POKé"
            elif b == 0xE2:  # MN
                result += "MON"
            elif b == 0xE3:  # -
                result += "-"
            elif b == 0xE4:  # 'r
                result += "'r"
            elif b == 0xE5:  # 'm
                result += "'m"
            elif b == 0xE6:  # ?
                result += "?"
            elif b == 0xE7:  # !
                result += "!"
            elif b == 0xE8:  # .
                result += "."
            elif b == 0xE9:  # ア
                result += "ア"
            elif b == 0xEA:  # ウ
                result += "ウ"
            elif b == 0xEB:  # エ
                result += "エ"
            elif b == 0xEC:  # ▷
                result += "▷"
            elif b == 0xED:  # ►
                result += "►"
            elif b == 0xEE:  # ▼
                result += "▼"
            elif b == 0xEF:  # ♂
                result += "♂"
            # F-register special characters
            elif b == 0xF0:  # ♭
                result += "♭"
            elif b == 0xF1:  # ×
                result += "×"
            elif b == 0xF2:  # .
                result += "."
            elif b == 0xF3:  # /
                result += "/"
            elif b == 0xF4:  # ,
                result += ","
            elif b == 0xF5:  # ♀
                result += "♀"
            # Numbers 0-9 (0xF6-0xFF)
            elif 0xF6 <= b <= 0xFF:
                result += str(b - 0xF6)
            else:
                # For debugging, show the hex value of unknown characters
                result += f"[{b:02X}]"
        return result.strip()

    def read_player_name(self) -> str:
        """Read the player's name"""
        name_bytes = self.memory[0xD158:0xD163]
        return self._convert_text(name_bytes)

    def read_rival_name(self) -> str:
        """Read rival's name"""
        name_bytes = self.memory[0xD34A:0xD351]
        return self._convert_text(name_bytes)

    def read_badges(self) -> list[str]:
        """Read obtained badges as list of names"""
        badge_byte = self.memory[0xD356]
        badges = []

        if badge_byte & Badge.BOULDER:
            badges.append("BOULDER")
        if badge_byte & Badge.CASCADE:
            badges.append("CASCADE")
        if badge_byte & Badge.THUNDER:
            badges.append("THUNDER")
        if badge_byte & Badge.RAINBOW:
            badges.append("RAINBOW")
        if badge_byte & Badge.SOUL:
            badges.append("SOUL")
        if badge_byte & Badge.MARSH:
            badges.append("MARSH")
        if badge_byte & Badge.VOLCANO:
            badges.append("VOLCANO")
        if badge_byte & Badge.EARTH:
            badges.append("EARTH")

        return badges

    def read_party_size(self) -> int:
        """Read number of Pokemon in party"""
        return self.memory[0xD163]

    def read_party_pokemon(self) -> list[PokemonData]:
        """Read all Pokemon currently in the party with full data"""
        party = []
        party_size = self.read_party_size()

        # Base addresses for party Pokemon data
        base_addresses = [0xD16B, 0xD197, 0xD1C3, 0xD1EF, 0xD21B, 0xD247]
        nickname_addresses = [0xD2B5, 0xD2C0, 0xD2CB, 0xD2D6, 0xD2E1, 0xD2EC]

        for i in range(party_size):
            addr = base_addresses[i]

            # Read experience (3 bytes)
            exp = (
                (self.memory[addr + 0x1A] << 16)
                + (self.memory[addr + 0x1B] << 8)
                + self.memory[addr + 0x1C]
            )

            # Read moves and PP
            moves = []
            move_pp = []
            for j in range(4):
                move_id = self.memory[addr + 8 + j]
                if move_id != 0:
                    moves.append(Move(move_id).name.replace("_", " "))
                    move_pp.append(self.memory[addr + 0x1D + j])

            # Read nickname
            nickname = self._convert_text(
                self.memory[nickname_addresses[i] : nickname_addresses[i] + 11]
            )

            type1 = PokemonType(self.memory[addr + 5])
            type2 = PokemonType(self.memory[addr + 6])
            # If both types are the same, only show one type
            if type1 == type2:
                type2 = None

            try:
                species_id = self.memory[addr]
                species_name = Pokemon(species_id).name.replace("_", " ")
            except ValueError:
                continue
            status_value = self.memory[addr + 4]
            
            pokemon = PokemonData(
                species_id=self.memory[addr],
                species_name=species_name,
                current_hp=(self.memory[addr + 1] << 8) + self.memory[addr + 2],
                max_hp=(self.memory[addr + 0x22] << 8) + self.memory[addr + 0x23],
                level=self.memory[addr + 0x21],  # Using actual level
                status=StatusCondition(status_value),
                type1=type1,
                type2=type2,
                moves=moves,
                move_pp=move_pp,
                trainer_id=(self.memory[addr + 12] << 8) + self.memory[addr + 13],
                nickname=nickname,
                experience=exp,
            )
            party.append(pokemon)

        return party

    def read_game_time(self) -> tuple[int, int, int]:
        """Read game time as (hours, minutes, seconds)"""
        hours = (self.memory[0xDA40] << 8) + self.memory[0xDA41]
        minutes = self.memory[0xDA42]
        seconds = self.memory[0xDA44]
        return (hours, minutes, seconds)

    def read_location(self) -> str:
        """Read current location name"""
        map_id = self.memory[0xD35E]
        return MapLocation(map_id).name.replace("_", " ")

    def read_tileset(self) -> str:
        """Read current map's tileset name"""
        tileset_id = self.memory[0xD367]
        return Tileset(tileset_id).name.replace("_", " ")

    def read_coordinates(self) -> tuple[int, int]:
        """Read player's current X,Y coordinates"""
        return (self.memory[0xD362], self.memory[0xD361])

    def read_coins(self) -> int:
        """Read game corner coins"""
        return (self.memory[0xD5A4] << 8) + self.memory[0xD5A5]

    def read_item_count(self) -> int:
        """Read number of items in inventory"""
        return self.memory[0xD31D]

    def read_items(self) -> list[tuple[str, int]]:
        """Read all items in inventory with proper item names"""
        # Revised mapping based on the game's internal item numbering
        
        items = []
        count = self.read_item_count()

        for i in range(count):
            item_id = self.memory[0xD31E + (i * 2)]
            quantity = self.memory[0xD31F + (i * 2)]

            # Handle TMs (0xC9-0xFE)
            if 0xC9 <= item_id <= 0xFE:
                tm_num = item_id - 0xC8
                item_name = f"TM{tm_num:02d}"
            elif 0xC4 <= item_id <= 0xC8:
                hm_num = item_id - 0xC3
                item_name = f"HM{hm_num:02d}"
            elif item_id in ITEM_NAMES:
                item_name = ITEM_NAMES[item_id]
            else:
                item_name = f"UNKNOWN_{item_id:02X}"

            items.append((item_name, quantity))

        return items

    def read_dialog(self) -> str:
        """Read any dialog text currently on screen by scanning the tilemap buffer"""
        # Tilemap buffer is from C3A0 to C507
        buffer_start = 0xC3A0
        buffer_end = 0xC507

        # Get all bytes from the buffer
        buffer_bytes = [self.memory[addr] for addr in range(buffer_start, buffer_end)]

        # Look for sequences of text (ignoring long sequences of 0x7F/spaces)
        text_lines = []
        current_line = []
        space_count = 0
        last_was_border = False

        for b in buffer_bytes:
            if b == 0x7C:  # ║ character
                if last_was_border:
                    # If the last character was a border and this is ║, treat as newline
                    text = self._convert_text(current_line)
                    if text.strip():
                        text_lines.append(text)
                    current_line = []
                    space_count = 0
                else:
                    # current_line.append(b)
                    pass
                last_was_border = True
            elif b == 0x7F:  # Space
                space_count += 1
                current_line.append(b)  # Always keep spaces
                last_was_border = False
            # All text characters: uppercase, lowercase, special chars, punctuation, symbols
            elif (
                # Box drawing (0x79-0x7E)
                # (0x79 <= b <= 0x7E)
                # or
                # Uppercase (0x80-0x99)
                (0x80 <= b <= 0x99)
                or
                # Punctuation (0x9A-0x9F)
                (0x9A <= b <= 0x9F)
                or
                # Lowercase (0xA0-0xB9)
                (0xA0 <= b <= 0xB9)
                or
                # Contractions (0xBA-0xBF)
                (0xBA <= b <= 0xBF)
                or
                # Special characters in E-row (0xE0-0xEF)
                (0xE0 <= b <= 0xEF)
                or
                # Special characters in F-row (0xF0-0xF5)
                (0xF0 <= b <= 0xF5)
                or
                # Numbers (0xF6-0xFF)
                (0xF6 <= b <= 0xFF)
                or
                # Line break
                b == 0x4E
            ):
                space_count = 0
                current_line.append(b)
                last_was_border = (
                    0x79 <= b <= 0x7E
                )  # Track if this is a border character

            # If we see a lot of spaces, might be end of line
            if space_count > 10 and current_line:
                text = self._convert_text(current_line)
                if text.strip():  # Only add non-empty lines
                    text_lines.append(text)
                current_line = []
                space_count = 0
                last_was_border = False

        # Add final line if any
        if current_line:
            text = self._convert_text(current_line)
            if text.strip():
                text_lines.append(text)

        text = "\n".join(text_lines)

        # Post-process for name entry context
        if "lower case" in text.lower() or "UPPER CASE" in text:
            # We're in name entry, replace ♭ with ED
            text = text.replace("♭", "ED\n")

        return text

    def read_pokedex_caught_count(self) -> int:
        """Read how many unique Pokemon species have been caught"""
        # Pokedex owned flags are stored in D2F7-D309
        # Each byte contains 8 flags for 8 Pokemon
        # Total of 19 bytes = 152 Pokemon
        caught_count = 0
        for addr in range(0xD2F7, 0xD30A):
            byte = self.memory[addr]
            # Count set bits in this byte
            caught_count += bin(byte).count("1")
        return caught_count
