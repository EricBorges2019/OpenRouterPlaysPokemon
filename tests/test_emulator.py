import unittest
import numpy as np
from agent.emulator import Emulator

class TestEmulatorDownsample(unittest.TestCase):
    def test_downsample_array_basic(self):
        """Test with all zeros to ensure shape is correct."""
        arr = np.zeros((18, 20))
        # We pass None as self since it's not used in the method
        result = Emulator._downsample_array(None, arr)
        self.assertEqual(result.shape, (9, 10))
        self.assertTrue(np.all(result == 0))

    def test_downsample_array_ones(self):
        """Test with all ones to ensure mean calculation is correct."""
        arr = np.ones((18, 20))
        result = Emulator._downsample_array(None, arr)
        self.assertEqual(result.shape, (9, 10))
        np.testing.assert_allclose(result, 1.0)

    def test_downsample_array_averaging(self):
        """Test with specific values to verify 2x2 block averaging."""
        arr = np.zeros((18, 20))
        # Fill first 2x2 block:
        # [[1, 2],
        #  [3, 4]] -> mean = (1+2+3+4)/4 = 10/4 = 2.5
        arr[0, 0] = 1
        arr[0, 1] = 2
        arr[1, 0] = 3
        arr[1, 1] = 4

        # Fill another 2x2 block at (2, 2) [which becomes (1, 1) in downsampled]:
        # [[10, 20],
        #  [30, 40]] -> mean = (10+20+30+40)/4 = 100/4 = 25.0
        arr[2, 2] = 10
        arr[2, 3] = 20
        arr[3, 2] = 30
        arr[3, 3] = 40

        # Fill a block at the very end:
        # [[100, 100],
        #  [0, 0]] -> mean = 50.0
        arr[16, 18] = 100
        arr[16, 19] = 100
        arr[17, 18] = 0
        arr[17, 19] = 0

        result = Emulator._downsample_array(None, arr)
        self.assertAlmostEqual(result[0, 0], 2.5)
        self.assertAlmostEqual(result[1, 1], 25.0)
        self.assertAlmostEqual(result[8, 9], 50.0)

    def test_downsample_array_large_values(self):
        """Test with large values to ensure no overflow issues."""
        arr = np.full((18, 20), 1000.0)
        result = Emulator._downsample_array(None, arr)
        np.testing.assert_allclose(result, 1000.0)

    def test_downsample_array_invalid_shape(self):
        """Test that incorrect input shapes raise ValueError."""
        invalid_shapes = [
            (17, 20),
            (18, 19),
            (9, 10),
            (36, 40)
        ]
        for shape in invalid_shapes:
            with self.subTest(shape=shape):
                arr = np.zeros(shape)
                with self.assertRaisesRegex(ValueError, "Input array must be 18x20"):
                    Emulator._downsample_array(None, arr)

    def test_downsample_array_type_error(self):
        """Test that non-numpy arrays with similar interface also work, or fail gracefully."""
        # This might fail if the input doesn't have .reshape or .mean
        with self.assertRaises(AttributeError):
            Emulator._downsample_array(None, [[0]*20]*18)

if __name__ == '__main__':
    unittest.main()
