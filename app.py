from PyQt6.QtWidgets import (
    QMainWindow,
    QPushButton,
    QGridLayout,
    QWidget,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QFileDialog,
)
from PyQt6.QtGui import QPixmap, QPainter, QColor, QPen
from PyQt6.QtCore import QSize, Qt
from .data import RegisteredStream, Connection


class NewStreamDialog(QDialog):
    """Dialog box for registering a new stream.

    Args:
        connection (Connection): connection to the data, to register the new stream to.
        parent (QWidget | None): parent widget, optional. Defaults to None.
    """

    def __init__(self, connection: Connection, parent=None):
        super().__init__(parent)
        self._connection = connection
        self.setWindowTitle("Add a new stream")
        layout = QGridLayout()

        message = QLabel("Fill in the details below to add a streamer!")
        layout.addWidget(message, 0, 0, 1, 3, Qt.AlignmentFlag.AlignLeft)

        name_msg = QLabel("Streamer Name:")
        self._name_field = QLineEdit()
        layout.addWidget(name_msg, 1, 0, 1, 1, Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self._name_field, 1, 1, 1, 2)

        URL_msg = QLabel("Streamer URL:")
        self._URL_field = QLineEdit()
        layout.addWidget(URL_msg, 2, 0, 1, 1, Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self._URL_field, 2, 1, 1, 2)

        icon_msg = QLabel("Icon:")
        self._icon_button = NewFileDialog(self)
        layout.addWidget(icon_msg, 3, 0, 1, 1, Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self._icon_button, 3, 1, 1, 2)

        QBtn = (
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )

        self.buttonBox = QDialogButtonBox(QBtn)
        self.buttonBox.accepted.connect(self.parse_response)
        self.buttonBox.rejected.connect(self.reject)
        layout.addWidget(self.buttonBox, 4, 0, 1, 3)
        self.setLayout(layout)

    def parse_response(self):
        url = self._URL_field.text()
        display_name = self._name_field.text()  # May be empty
        icon_path = self._icon_button._file  # May be None
        result = RegisteredStream.from_url(url, display_name, icon_path)
        self._connection.add_stream(result)
        self.accept()


class NewFileDialog(QPushButton):
    """Button that opens a file dialog to select an icon. Saves selected file in :attr:`_file`

    Args:
        parent (QWidget | None): parent widget, optional. Defaults to None.
    """

    def __init__(self, parent=None):
        super().__init__("select icon", parent=parent)
        self.clicked.connect(self.click_action)
        self._file = None

    def click_action(self):
        file_dialog = QFileDialog()
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        file_dialog.setNameFilter("Images (*.png *.jpg)")
        if file_dialog.exec():
            self._file = file_dialog.selectedFiles()[0]


class NewStreamButton(QPushButton):
    """Button that creats a dialog for registering a new stream.

    Args:
        connection (Connection): connection to the data, to register the new stream to.
        parent (QWidget | None): parent widget, optional. Defaults to None.
    """

    def __init__(self, connection, update_fn, parent=None):
        super().__init__("Add Stream!", parent=parent)
        self._connection = connection
        self._update_fn = update_fn
        self.clicked.connect(self.click_action)

    def click_action(self):
        dialog_box = NewStreamDialog(self._connection, self.parent())
        print(self.parent())
        if dialog_box.exec():
            self._update_fn()


class StreamButton(QPushButton):
    """GUI representation of a :class:`RegisteredStream` object.

    Args:
        stream (RegisteredStream): the object it represents.
        parent (QWidget | None): parent widget, optional. Defaults to None.
    """

    def __init__(self, stream: RegisteredStream, parent=None):

        super().__init__(stream.display_name, parent=parent)
        self._stream = stream
        self._pixmap = self._create_pixmap()
        self.clicked.connect(self.click_action)

    def paintEvent(self, event):  # type: ignore
        painter = QPainter(self)
        painter.drawPixmap(event.rect(), self._pixmap)

    def click_action(self):
        self._stream.start()

    def _create_pixmap(self):
        if (icon_path := self._stream.get_icon_path()) is not None:
            pixmap = QPixmap(icon_path)
        else:
            pixmap = QPixmap(70, 70)
            pixmap.fill(QColor("lightblue"))
            painter = QPainter(pixmap)
            pen = QPen(QColor("black"))
            font = painter.font()
            font.setPixelSize(12)
            painter.setFont(font)
            painter.setPen(pen)
            painter.drawText(
                pixmap.rect(), Qt.AlignmentFlag.AlignCenter, self._stream.display_name
            )
        return pixmap

    def sizeHint(self):
        return self._pixmap.size()


class MainWindow(QMainWindow):
    """Main window of the GUI.

    Args:
        connection (Connection): connection to the underlying data, used for saving and loading.
    """

    def __init__(self, connection: Connection):
        super().__init__()

        self.setWindowTitle("Streamlink GUI")
        self._connection = connection
        self._layout = QGridLayout()
        self._container = QWidget()

        self._set_layout()
        self.setCentralWidget(self._container)

    def _set_layout(self):
        streams = self._connection.get_streams()
        n_rows = len(streams) // 5 + ((len(streams) % 5) > 0)
        n_cols = len(streams) // n_rows + ((len(streams) % n_rows) > 0)
        add_stream_button = NewStreamButton(
            self._connection, self.update_streams, parent=self
        )
        self._layout.addWidget(
            add_stream_button, 0, 0, 1, n_cols, Qt.AlignmentFlag.AlignHCenter
        )
        for ind, stream in enumerate(streams):
            row = ind % n_rows + 1
            col = ind // n_rows
            button = StreamButton(stream, parent=self)
            self._layout.addWidget(button, row, col)

        self._container.setLayout(self._layout)

    def _reset_layout(self):
        while self._layout.count():
            widget = self._layout.takeAt(0).widget()  # type: ignore
            widget.deleteLater()  # type: ignore

    def update_streams(self):
        """Redraw the layout with updated registered streams."""
        self._reset_layout()
        self._set_layout()

    def closeEvent(self, a0):
        self._connection.finish()
