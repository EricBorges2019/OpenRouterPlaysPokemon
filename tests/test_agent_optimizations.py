import unittest
import numpy as np
import sys
import os

# Add the current directory to sys.path so we can import agent
sys.path.append(os.getcwd())

from agent.memory_reader import PokemonRedReader
from agent.emulator import Emulator

class MockMemory:
    def __init__(self, data, default_val=0):
        self.data = data
        self.default_val = default_val
    def __getitem__(self, key):
        if isinstance(key, slice):
            return [self.data.get(i, self.default_val) for i in range(key.start, key.stop)]
        return self.data.get(key, self.default_val)

class TestAgentOptimizations(unittest.TestCase):
    def test_get_direction(self):
        # Create a mock emulator (we don't need a real ROM for this test)
        # We'll just test the _get_direction method directly
        emu = Emulator.__new__(Emulator)

        # Test 'down' pattern [0, 1, 2, 3] at (5, 5)
        arr = np.ones((18, 20), dtype=int) * 255
        arr[5, 5] = 0
        arr[5, 6] = 1
        arr[6, 5] = 2
        arr[6, 6] = 3
        self.assertEqual(emu._get_direction(arr), "down")

        # Test 'up' pattern [4, 5, 6, 7] at (10, 10)
        arr = np.ones((18, 20), dtype=int) * 255
        arr[10, 10] = 4
        arr[10, 11] = 5
        arr[11, 10] = 6
        arr[11, 11] = 7
        self.assertEqual(emu._get_direction(arr), "up")

        # Test 'right' pattern [9, 8, 11, 10]
        arr = np.ones((18, 20), dtype=int) * 255
        arr[2, 2] = 9
        arr[2, 3] = 8
        arr[3, 2] = 11
        arr[3, 3] = 10
        self.assertEqual(emu._get_direction(arr), "right")

        # Test 'left' pattern [8, 9, 10, 11]
        arr = np.ones((18, 20), dtype=int) * 255
        arr[15, 15] = 8
        arr[15, 16] = 9
        arr[16, 15] = 10
        arr[16, 16] = 11
        self.assertEqual(emu._get_direction(arr), "left")

        # Test 'no direction found'
        arr = np.ones((18, 20), dtype=int) * 255
        self.assertEqual(emu._get_direction(arr), "no direction found")

    def test_read_items(self):
        # Mock memory for items
        mem_data = {0xD31D: 2, 0xD31E: 0x01, 0xD31F: 5, 0xD320: 0x04, 0xD321: 10}
        reader = PokemonRedReader(MockMemory(mem_data))

        items = reader.read_items()
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0], ("MASTER BALL", 5))
        self.assertEqual(items[1], ("POKé BALL", 10))

    def test_read_dialog_slicing(self):
        # Mock memory for dialog
        buffer_start = 0xC3A0
        mem_data = {}
        # H=0x87, E=0x84, L=0x8B, O=0x8E
        mem_data[buffer_start] = 0x7C
        mem_data[buffer_start + 1] = 0x87
        mem_data[buffer_start + 2] = 0x84
        mem_data[buffer_start + 3] = 0x8B
        mem_data[buffer_start + 4] = 0x8B
        mem_data[buffer_start + 5] = 0x8E
        mem_data[buffer_start + 6] = 0x7C
        mem_data[buffer_start + 7] = 0x7C

        reader = PokemonRedReader(MockMemory(mem_data, default_val=0x7F))
        dialog = reader.read_dialog()
        self.assertIn("HELLO", dialog)

    def test_read_pokedex_caught_count(self):
        mem_data = {0xD2F7: 0x01, 0xD2F8: 0x03}
        reader = PokemonRedReader(MockMemory(mem_data))
        self.assertEqual(reader.read_pokedex_caught_count(), 3)

if __name__ == "__main__":
    unittest.main()
