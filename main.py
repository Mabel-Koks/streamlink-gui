import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon

from .app import MainWindow
from .data import JSONConnection
from .data.exceptions import UnsupportedError

# start application
app = QApplication(sys.argv)
app.setApplicationName("Streamlink GUI")
icon = QIcon(str(Path(__file__).parent / "data" / "streamlink_icon.png"))
app.setWindowIcon(icon)

# parse backend
try:
    entrypoint = Path(sys.argv[1])
except IndexError:
    entrypoint = Path(__file__).parent / "data" / "streams.json"

suffix = entrypoint.name.split(".")[-1]

if suffix == "json":
    connection = JSONConnection(entrypoint)
elif suffix == "sql":
    raise UnsupportedError("SQL backend is not yet supported.", (entrypoint, suffix))
else:
    raise UnsupportedError(
        f"Unknown entrypoint type {entrypoint}", (entrypoint, __name__)
    )

# create GUI
window = MainWindow(connection)
window.show()

app.exec()
