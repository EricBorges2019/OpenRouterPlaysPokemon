import unittest
from agent.memory_reader import PokemonRedReader

class MockMemory:
    def __init__(self, data=None):
        self.data = data or [0] * 0x10000
    def __getitem__(self, key):
        return self.data[key]
    def __setitem__(self, key, value):
        self.data[key] = value

class TestMemoryReader(unittest.TestCase):
    def setUp(self):
        self.memory = MockMemory()
        self.reader = PokemonRedReader(self.memory)

    def test_convert_text(self):
        # A-Z
        self.assertEqual(self.reader._convert_text([0x80, 0x81, 0x82]), "ABC")
        # a-z
        self.assertEqual(self.reader._convert_text([0xA0, 0xA1, 0xA2]), "abc")
        # Numbers
        self.assertEqual(self.reader._convert_text([0xF6, 0xF7, 0xF8]), "012")
        # Space
        self.assertEqual(self.reader._convert_text([0x7F]), "") # strip() makes it empty if it's only space
        self.assertEqual(self.reader._convert_text([0x80, 0x7F, 0x81]), "A B")
        # Special characters
        self.assertEqual(self.reader._convert_text([0x54]), "POKé")
        # According to original implementation, 0xE1 first matches "Pk"
        self.assertEqual(self.reader._convert_text([0xE1]), "Pk")
        # 0xE2 first matches "Mn"
        self.assertEqual(self.reader._convert_text([0xE2]), "Mn")
        # End marker
        self.assertEqual(self.reader._convert_text([0x80, 0x50, 0x81]), "A")

    def test_read_pokedex_caught_count(self):
        # D2F7 to D309
        self.memory[0xD2F7] = 0b00000001
        self.memory[0xD2F8] = 0b00000011
        self.assertEqual(self.reader.read_pokedex_caught_count(), 3)

        self.memory[0xD309] = 0b11111111
        # 1 + 2 + 8 = 11
        self.assertEqual(self.reader.read_pokedex_caught_count(), 11)

if __name__ == "__main__":
    unittest.main()
