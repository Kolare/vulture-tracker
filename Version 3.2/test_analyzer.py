import unittest
import numpy as np
import cv2
import math
from datetime import datetime

from analyzer import HealthAnalyzer

class TestHealthAnalyzer(unittest.TestCase):

    SAMPLE_RADII = [19, 20, 21]

    def _create_mock_image(self, health_percent, width=200, height=200):
        """Creates a mock image with a health bar for testing."""
        image = np.zeros((height, width, 3), dtype=np.uint8)
        center_x, center_y = width // 2, height // 2

        if health_percent > 0:
            health_color = (0, 255, 0) # BGR
            arc_angle_degrees = 360 * (health_percent / 100.0)

            for i in range(int(arc_angle_degrees * 4)): # 4 steps per degree
                angle = i / 4.0
                rad = math.radians(angle)
                for radius in self.SAMPLE_RADII:
                    x = int(round(center_x + radius * math.sin(rad)))
                    y = int(round(center_y - radius * math.cos(rad)))
                    if 0 <= x < width and 0 <= y < height:
                        image[y, x] = health_color

        return image

    def test_100_percent_health(self):
        """Test with a full health bar."""
        mock_image = self._create_mock_image(100)
        result = HealthAnalyzer.analyze(mock_image)
        self.assertIsInstance(result, dict)
        self.assertAlmostEqual(result['health_percent'], 100.0, delta=2.0)
        self.assertIn('timestamp', result)
        self.assertIsInstance(result['timestamp'], datetime)
        self.assertIn('center_crop', result)
        self.assertEqual(result['center_crop'].shape, (50, 50, 3))

    def test_75_percent_health(self):
        """Test with a 75% health bar."""
        mock_image = self._create_mock_image(75)
        result = HealthAnalyzer.analyze(mock_image)
        self.assertIsInstance(result, dict)
        self.assertAlmostEqual(result['health_percent'], 75.0, delta=2.0)

    def test_50_percent_health(self):
        """Test with a 50% health bar."""
        mock_image = self._create_mock_image(50)
        result = HealthAnalyzer.analyze(mock_image)
        self.assertIsInstance(result, dict)
        self.assertAlmostEqual(result['health_percent'], 50.0, delta=2.0)

    def test_25_percent_health(self):
        """Test with a 25% health bar."""
        mock_image = self._create_mock_image(25)
        result = HealthAnalyzer.analyze(mock_image)
        self.assertIsInstance(result, dict)
        self.assertAlmostEqual(result['health_percent'], 25.0, delta=2.0)

    def test_wrecked_status(self):
        """Test that 0% health returns 'wrecked' status."""
        empty_image = np.zeros((200, 200, 3), dtype=np.uint8)
        result = HealthAnalyzer.analyze(empty_image)
        self.assertEqual(result['health_percent'], 'wrecked')

    def test_return_structure_and_crop(self):
        """Test the structure of the returned dictionary and the center crop."""
        mock_image = self._create_mock_image(50, width=202, height=202)
        center_x, center_y = 101, 101
        mock_image[center_y, center_x] = (42, 42, 42)

        result = HealthAnalyzer.analyze(mock_image)

        self.assertIsInstance(result, dict)
        self.assertIn('health_percent', result)
        self.assertIn('timestamp', result)
        self.assertIn('center_crop', result)

        self.assertIsInstance(result['timestamp'], datetime)

        crop = result['center_crop']
        self.assertIsInstance(crop, np.ndarray)
        self.assertEqual(crop.shape, (50, 50, 3))

        crop_center_pixel = crop[25, 25]
        np.testing.assert_array_equal(crop_center_pixel, [42, 42, 42])

if __name__ == '__main__':
    unittest.main()