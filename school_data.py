from threading import RLock


class SchoolData:
    def __init__(self):
        self._lock = RLock()
        self._next_id = 3
        self._lessons = {
            1: {
                "id": 1,
                "student": "Asha",
                "instrument": "Piano",
                "date": "2026-10-20",
                "duration": 30,
                "teacher": "Mr Rao",
                "notes": "",
            },
            2: {
                "id": 2,
                "student": "Rahul",
                "instrument": "Guitar",
                "date": "2026-10-21",
                "duration": 45,
                "teacher": "Ms Devi",
                "notes": "",
            },
        }

    def list_lessons(self):
        with self._lock:
            return [dict(x) for x in self._lessons.values()]

    def get_lesson(self, lesson_id):
        with self._lock:
            lesson = self._lessons.get(lesson_id)
            return dict(lesson) if lesson else None

    def create_lesson(self, data):
        with self._lock:
            lesson = dict(data)
            lesson["id"] = self._next_id
            self._next_id += 1
            self._lessons[lesson["id"]] = lesson
            return dict(lesson)

    def update_lesson(self, lesson_id, data):
        with self._lock:
            if lesson_id not in self._lessons:
                return None

            lesson = dict(self._lessons[lesson_id])
            lesson.update(data)
            lesson["id"] = lesson_id
            self._lessons[lesson_id] = lesson
            return dict(lesson)

    def delete_lesson(self, lesson_id):
        with self._lock:
            return self._lessons.pop(lesson_id, None) is not None