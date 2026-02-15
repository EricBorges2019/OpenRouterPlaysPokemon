import unittest
from agent.memory_reader import PokemonRedReader

class MockMemory:
    def __init__(self, data):
        self.data = data
    def __getitem__(self, key):
        if isinstance(key, slice):
            return self.data[key.start:key.stop]
        return self.data[key]

class TestPokemonRedReader(unittest.TestCase):
    def setUp(self):
        self.mock_data = [0] * 0x10000
        self.memory = MockMemory(self.mock_data)
        self.reader = PokemonRedReader(self.memory)

    def test_convert_text(self):
        # A-Z
        self.assertEqual(self.reader._convert_text([0x80, 0x81, 0x82]), "ABC")
        # a-z
        self.assertEqual(self.reader._convert_text([0xA0, 0xA1, 0xA2]), "abc")
        # Numbers
        self.assertEqual(self.reader._convert_text([0xF6, 0xF7, 0xF8]), "012")
        # Special characters
        self.assertEqual(self.reader._convert_text([0x7F, 0x54]), "POKé") # Space is stripped by .strip()
        # End marker
        self.assertEqual(self.reader._convert_text([0x80, 0x50, 0x81]), "A")
        # Unknown character
        self.assertEqual(self.reader._convert_text([0x00]), "[00]")

    def test_read_items(self):
        self.mock_data[0xD31D] = 2
        self.mock_data[0xD31E] = 0x01 # MASTER BALL
        self.mock_data[0xD31F] = 5
        self.mock_data[0xD320] = 0xC9 # TM01
        self.mock_data[0xD321] = 1

        items = self.reader.read_items()
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0], ("MASTER BALL", 5))
        self.assertEqual(items[1], ("TM01", 1))

    def test_read_pokedex_caught_count(self):
        self.mock_data[0xD2F7] = 0b10101010 # 4 bits set
        self.mock_data[0xD2F8] = 0b00000001 # 1 bit set
        # Others are 0
        self.assertEqual(self.reader.read_pokedex_caught_count(), 5)

if __name__ == "__main__":
    unittest.main()
