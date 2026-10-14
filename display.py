def display_lesson(lesson):
    if not lesson:
        print("No lesson found.")
        return

    for field in (
        "id", "student", "instrument", "date",
        "duration", "teacher", "notes",
    ):
        print(f"{field.capitalize()}: {lesson.get(field, '')}")


def display_lessons(lessons):
    if not lessons:
        print("No lessons scheduled.")
        return

    columns = (
        ("id", "ID"),
        ("student", "Student"),
        ("instrument", "Instrument"),
        ("date", "Date"),
        ("duration", "Minutes"),
        ("teacher", "Teacher"),
    )

    widths = [max(len(label), 8) for _, label in columns]

    print(" | ".join(
        label.ljust(widths[i])
        for i, (_, label) in enumerate(columns)
    ))
    print("-+-".join("-" * width for width in widths))

    for lesson in lessons:
        print(" | ".join(
            str(lesson.get(key, "")).ljust(widths[i])
            for i, (key, _) in enumerate(columns)
        ))