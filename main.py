import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from .app import MainWindow
from .data import JSONConnection

app = QApplication(sys.argv)

try:
    json_path = Path(sys.argv[1])
except IndexError:
    json_path = Path(__file__).parent / "data" / "streams.json"
connection = JSONConnection(json_path)
window = MainWindow(connection)
window.show()

app.exec()
