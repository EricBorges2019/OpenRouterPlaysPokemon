# Bolt's Journal - Critical Learnings

## 2025-05-22 - PyBoy Memory Reading Optimization
**Learning:** In the PyBoy emulator environment, accessing memory through individual index lookups in a loop (e.g., `[self.memory[addr] for addr in range(start, end)]`) is significantly slower than using slicing (`self.memory[start:end]`). Slicing is handled at the C level in PyBoy/memoryview, providing a major speed boost for bulk reads like tilemaps or buffers.
**Action:** Always prefer slicing for contiguous memory reads in `PokemonRedReader` or similar memory-mapped IO components.

## 2025-05-22 - Static Mapping Hoisting
**Learning:** Python re-creates dictionaries and lists defined within function scopes on every call. For frequently called state extraction methods, this adds unnecessary overhead.
**Action:** Move static mappings (like `ITEM_NAMES`) and address lists to class-level constants to ensure they are only created once at class definition time.
