## 2025-05-22 - Memory Reader Optimizations
**Learning:** In the PyBoy environment, bulk memory reads using slicing (`self.memory[start:end]`) are significantly more efficient than individual byte access or list comprehensions. Additionally, replacing long `if/elif` chains (like the character mapping in `_convert_text`) with a pre-calculated dictionary lookup provides a measurable speed boost during frequent game state extractions.
**Action:** Always prefer slicing for contiguous memory reads and use static mappings (class constants) for repetitive data structure creation or lookup logic.
