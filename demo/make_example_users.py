"""Write demo/example-users.xlsx, the user list the app looks people up in.

    python demo/make_example_users.py

Each row is one person: name, personal number, department. The app takes the
personal number from the Windows logon name and finds the row, so nobody is
asked to fill anything in.
"""
import os
import sys

USERS = [
    ("R. Levi", "8123456", "Avionics"),
    ("D. Cohen", "8123457", "Avionics"),
    ("M. Azoulay", "8200011", "Logistics"),
    ("Y. Barak", "8200012", "Logistics"),
    ("N. Shapira", "8311122", "Maintenance"),
]

HEADERS = ["Name", "Personal number", "Department"]


def main(path):
    import openpyxl
    from openpyxl.styles import Alignment, Font, PatternFill

    book = openpyxl.Workbook()
    sheet = book.active
    sheet.title = "Users"
    sheet.append(HEADERS)
    fill = PatternFill("solid", fgColor="E8EEF7")
    for column in range(1, len(HEADERS) + 1):
        cell = sheet.cell(row=1, column=column)
        cell.font = Font(bold=True)
        cell.fill = fill
        cell.alignment = Alignment(vertical="center")

    for user in USERS:
        sheet.append(list(user))
    # Text, so a long personal number is never shown as 8.12346E+06.
    for row in range(2, len(USERS) + 2):
        sheet.cell(row=row, column=2).number_format = "@"

    for column, width in zip("ABC", (26, 18, 20)):
        sheet.column_dimensions[column].width = width
    sheet.freeze_panes = sheet.cell(row=2, column=1)
    book.save(path)
    print(f"wrote {path}")


if __name__ == "__main__":
    default = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "example-users.xlsx")
    main(sys.argv[1] if len(sys.argv) > 1 else default)
