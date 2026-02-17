import unittest
from agent.memory_reader import PokemonRedReader, StatusCondition, PokemonType

class MockMemory:
    def __init__(self, data):
        self.data = data
    def __getitem__(self, key):
        if isinstance(key, slice):
            return self.data[key.start:key.stop]
        return self.data[key]

class TestMemoryReader(unittest.TestCase):
    def setUp(self):
        self.memory_data = [0] * 0x10000
        self.reader = PokemonRedReader(MockMemory(self.memory_data))

    def test_convert_text_basic(self):
        # "ABC" -> 0x80, 0x81, 0x82
        text_bytes = [0x80, 0x81, 0x82, 0x50]
        self.assertEqual(self.reader._convert_text(text_bytes), "ABC")

    def test_convert_text_special(self):
        # Space (0x7F), POKé (0x54)
        text_bytes = [0x80, 0x7F, 0x54, 0x50]
        self.assertEqual(self.reader._convert_text(text_bytes), "A POKé")

    def test_pokedex_caught_count(self):
        # 0xD2F7 to 0xD309 are pokedex caught flags
        self.memory_data[0xD2F7] = 0b10101010 # 4 caught
        self.memory_data[0xD2F8] = 0b00000001 # 1 caught
        # Other bytes remain 0
        self.assertEqual(self.reader.read_pokedex_caught_count(), 5)

    def test_read_dialog(self):
        # Tilemap buffer is from C3A0 to C507
        # Put some text in it: "║HELLO    ║"
        # ║ is 0x7C, space is 0x7F
        for i in range(0xC3A0, 0xC507):
            self.memory_data[i] = 0x7F

        self.memory_data[0xC3A0] = 0x7C # ║
        self.memory_data[0xC3A1] = 0x87 # H
        self.memory_data[0xC3A2] = 0x84 # E
        self.memory_data[0xC3A3] = 0x8B # L
        self.memory_data[0xC3A4] = 0x8B # L
        self.memory_data[0xC3A5] = 0x8E # O
        self.memory_data[0xC3A6] = 0x7F
        self.memory_data[0xC3A7] = 0x7F
        self.memory_data[0xC3A8] = 0x7C # ║

        # read_dialog skips the first border and looks for text
        # It should find "HELLO"
        self.assertEqual(self.reader.read_dialog().strip(), "HELLO")

if __name__ == "__main__":
    unittest.main()
