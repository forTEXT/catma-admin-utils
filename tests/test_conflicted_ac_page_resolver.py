import json
from unittest import TestCase
from unittest.mock import patch

from conflicted_ac_page_resolver import resolve


class Test(TestCase):
    @patch('builtins.print')
    def test_resolve(self, mock_print):
        # use a contrived conflicted annotation page file to test the resolve function
        resolve("conflicted_page.json")
        mock_print.assert_called_with("Mismatch in annotations with ID CATMA_EC4AAAB3-A65D-43E7-A966-67CDE70E636A")

        with open("merged_file", encoding="utf-8", newline=None) as merged_file:
            merged_annotations = json.load(merged_file)

        self.assertEqual(merged_annotations[0]["somethingunique"], "first")
        self.assertEqual(merged_annotations[1]["somethingunique"], "third")
        self.assertEqual(merged_annotations[2]["somethingunique"], "second")
        self.assertEqual(merged_annotations[3]["somethingunique"], "fourth")
        self.assertEqual(merged_annotations[4]["somethingunique"], "fifth-1")
        self.assertEqual(merged_annotations[5]["somethingunique"], "fifth-2")