import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from .app import MainWindow
from .data import JSONConnection

app = QApplication(sys.argv)

connection = JSONConnection(Path(sys.argv[1]))
window = MainWindow(connection)
window.show()

app.exec()
