import unittest
import time
from unittest.mock import MagicMock, patch

# Assuming the FallenRobot package is in the PYTHONPATH or installed
# If not, this might need adjustment based on how the project is structured
# For example, if tests are run from the project root:
# from FallenRobot.modules.helper_funcs.string_handling import extract_time
# Or, if PYTHONPATH needs to be adjusted:
# import sys
# sys.path.append('.') # Add project root to path
from FallenRobot.modules.helper_funcs.string_handling import extract_time

class TestExtractTime(unittest.TestCase):

    def setUp(self):
        # Create a mock message object for each test
        self.mock_message = MagicMock()
        # Mock the reply_text method that extract_time calls on error
        self.mock_message.reply_text = MagicMock()

    def test_valid_minutes(self):
        time_val = "5m"
        expected_bantime = int(time.time() + 5 * 60)
        actual_bantime = extract_time(self.mock_message, time_val)
        self.assertAlmostEqual(actual_bantime, expected_bantime, delta=1) # delta for slight time.time() differences
        self.mock_message.reply_text.assert_not_called()

    def test_valid_hours(self):
        time_val = "2h"
        expected_bantime = int(time.time() + 2 * 60 * 60)
        actual_bantime = extract_time(self.mock_message, time_val)
        self.assertAlmostEqual(actual_bantime, expected_bantime, delta=1)
        self.mock_message.reply_text.assert_not_called()

    def test_valid_days(self):
        time_val = "3d"
        expected_bantime = int(time.time() + 3 * 24 * 60 * 60)
        actual_bantime = extract_time(self.mock_message, time_val)
        self.assertAlmostEqual(actual_bantime, expected_bantime, delta=1)
        self.mock_message.reply_text.assert_not_called()

    def test_valid_weeks(self):
        time_val = "1w"
        expected_bantime = int(time.time() + 1 * 7 * 24 * 60 * 60)
        actual_bantime = extract_time(self.mock_message, time_val)
        self.assertAlmostEqual(actual_bantime, expected_bantime, delta=1)
        self.mock_message.reply_text.assert_not_called()

    def test_invalid_unit(self):
        time_val = "5x"
        result = extract_time(self.mock_message, time_val)
        self.assertEqual(result, "") # Expecting empty string on error
        self.mock_message.reply_text.assert_called_once()
        # Check the error message if desired, e.g.:
        # self.mock_message.reply_text.assert_called_with(
        #     "Invalid time type specified. Expected m, h, d, or w, got: x"
        # )


    def test_invalid_number(self):
        time_val = "xm"
        result = extract_time(self.mock_message, time_val)
        self.assertEqual(result, "")
        self.mock_message.reply_text.assert_called_once_with("Invalid time amount specified.")

    def test_no_unit(self):
        time_val = "5" # Missing unit
        result = extract_time(self.mock_message, time_val)
        self.assertEqual(result, "")
        self.mock_message.reply_text.assert_called_once()
        # Example check for the specific error message:
        # self.mock_message.reply_text.assert_called_with(
        #     "Invalid time type specified. Expected m, h, d, or w, got: 5"
        # )


    def test_no_number(self):
        time_val = "m" # Missing number
        result = extract_time(self.mock_message, time_val)
        self.assertEqual(result, "")
        self.mock_message.reply_text.assert_called_once_with("Invalid time amount specified.")

    def test_empty_input(self):
        time_val = "" # Empty input
        result = extract_time(self.mock_message, time_val)
        self.assertEqual(result, "")
        self.mock_message.reply_text.assert_called_once()
        # Check specific error message if desired:
        # self.mock_message.reply_text.assert_called_with(
        #    "Invalid time type specified. Expected m, h, d, or w, got: nothing"
        # )

    def test_zero_duration_minutes(self):
        time_val = "0m"
        expected_bantime = int(time.time()) # Duration is zero
        actual_bantime = extract_time(self.mock_message, time_val)
        self.assertAlmostEqual(actual_bantime, expected_bantime, delta=1)
        self.mock_message.reply_text.assert_not_called()

    def test_zero_duration_days(self):
        time_val = "0d"
        expected_bantime = int(time.time()) # Duration is zero
        actual_bantime = extract_time(self.mock_message, time_val)
        self.assertAlmostEqual(actual_bantime, expected_bantime, delta=1)
        self.mock_message.reply_text.assert_not_called()

if __name__ == '__main__':
    unittest.main()
