import unittest

from school_data import SchoolData


class TestSchoolData(unittest.TestCase):
    def setUp(self):
        self.store = SchoolData()

    def test_seed_lessons_exist(self):
        self.assertGreaterEqual(len(self.store.list_lessons()), 2)

    def test_create_and_get(self):
        lesson = self.store.create_lesson({
            "student": "Maya",
            "instrument": "Violin",
            "date": "2026-10-22",
            "duration": 30,
            "teacher": "Ms Rao",
            "notes": "",
        })

        found = self.store.get_lesson(lesson["id"])
        self.assertEqual(found["student"], "Maya")

    def test_update(self):
        updated = self.store.update_lesson(1, {"notes": "Bring a book"})
        self.assertEqual(updated["notes"], "Bring a book")

    def test_update_missing_lesson(self):
        self.assertIsNone(
            self.store.update_lesson(999, {"notes": "Missing"})
        )

    def test_delete(self):
        self.assertTrue(self.store.delete_lesson(1))
        self.assertIsNone(self.store.get_lesson(1))

    def test_delete_missing_lesson(self):
        self.assertFalse(self.store.delete_lesson(999))


if __name__ == "__main__":
    unittest.main()