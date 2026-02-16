import time
import timeit
import numpy as np
from agent.memory_reader import PokemonRedReader

# Mock memory view
class MockMemory:
    def __init__(self):
        self.data = np.zeros(0x10000, dtype=np.uint8)
    def __getitem__(self, key):
        return self.data[key]
    def __setitem__(self, key, value):
        self.data[key] = value

def benchmark():
    memory = MockMemory()
    reader = PokemonRedReader(memory)

    # Setup some data for _convert_text
    text_bytes = [0x80, 0x81, 0x82, 0xA0, 0xA1, 0xA2, 0xF6, 0xF7, 0xF8, 0x50]

    # Setup some data for read_dialog
    # Tilemap buffer is from C3A0 to C507
    for i in range(0xC3A0, 0xC507):
        memory[i] = 0x80 + (i % 20) # Just some characters

    # Setup some data for read_items
    memory[0xD31D] = 20 # 20 items
    for i in range(20):
        memory[0xD31E + (i * 2)] = 0x01 + i
        memory[0xD31F + (i * 2)] = 1

    # Setup some data for read_pokedex_caught_count
    for i in range(0xD2F7, 0xD30A):
        memory[i] = 0xAA # 10101010

    print("Benchmarking original implementation...")

    # Benchmark _convert_text
    convert_text_time = timeit.timeit(lambda: reader._convert_text(text_bytes), number=10000)
    print(f"_convert_text: {convert_text_time:.4f}s (10,000 calls)")

    # Benchmark read_dialog
    read_dialog_time = timeit.timeit(lambda: reader.read_dialog(), number=1000)
    print(f"read_dialog: {read_dialog_time:.4f}s (1,000 calls)")

    # Benchmark read_items
    read_items_time = timeit.timeit(lambda: reader.read_items(), number=1000)
    print(f"read_items: {read_items_time:.4f}s (1,000 calls)")

    # Benchmark read_pokedex_caught_count
    read_pokedex_time = timeit.timeit(lambda: reader.read_pokedex_caught_count(), number=10000)
    print(f"read_pokedex_caught_count: {read_pokedex_time:.4f}s (10,000 calls)")

if __name__ == "__main__":
    benchmark()
