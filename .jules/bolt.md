## 2025-05-14 - PyBoy Memory Reading Optimization
**Learning:** Bulk memory access in PyBoy via slicing `self.memory[start:end]` is significantly faster than iterative access via list comprehension. Additionally, text conversion using long `if/elif` chains can be replaced with O(1) dictionary lookups for a ~35% speedup.
**Action:** Always prefer slicing for bulk memory reads and pre-calculated mapping tables for frequent data translations.
