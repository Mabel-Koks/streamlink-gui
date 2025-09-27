import time

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
    QVBoxLayout,
    QPlainTextEdit,
)
from PyQt6.QtGui import QPixmap, QPainter, QColor, QPen
from PyQt6.QtCore import Qt, QProcess
from .data import RegisteredStream, Connection
from .data.exceptions import NoStreamError, ParseError


class LogDialog(QDialog):

    def __init__(self, error, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Logs")

        layout = QVBoxLayout()

        text = QLabel("Logs:")
        layout.addWidget(text)

        textbox = QPlainTextEdit(f"ERROR: {str(error)}")
        textbox.setReadOnly(True)
        layout.addWidget(textbox)

        button = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        layout.addWidget(button)
        button.rejected.connect(self.reject)

        self.setLayout(layout)


class ErrorDialog(QDialog):

    def __init__(self, error_message, error, extra_buttons=[], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Error...")

        self._error = error

        layout = QVBoxLayout()
        text = QLabel(error_message)
        layout.addWidget(text)

        buttonbox = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        more_info_button = QPushButton("Debug")
        more_info_button.clicked.connect(self._info_button_clicked)
        buttonbox.addButton(more_info_button, QDialogButtonBox.ButtonRole.ActionRole)
        [buttonbox.addButton(*ebut) for ebut in extra_buttons]
        buttonbox.rejected.connect(self.reject)
        layout.addWidget(buttonbox)

        self.setLayout(layout)

    def _info_button_clicked(self):
        LogDialog(self._error).exec()


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
        self._icon_button = FileDialogButton("select icon", parent=self)
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


class FileDialogButton(QPushButton):
    """Button that opens a file dialog to select an icon. Saves selected file in :attr:`_file`

    Args:
        button_text (str): text on the button.
        parent (QWidget | None): parent widget, optional. Defaults to None.
    """

    def __init__(self, button_text, parent=None):
        super().__init__(button_text, parent=parent)
        self.clicked.connect(self.click_action)
        self._file = None

    def click_action(self):
        file_dialog = QFileDialog()
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        file_dialog.setNameFilter("Images (*.png *.jpg)")
        if file_dialog.exec():
            self._file = file_dialog.selectedFiles()[0]


class NewStreamButton(QPushButton):
    """Button that creates a dialog for registering a new stream.

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
        if dialog_box.exec():
            self._update_fn()


class SRStatus:

    NOT_STARTED = 0
    RUNNING = 1
    RETRYING = 2
    STREAM_NOT_AVAILABLE = 3
    FINISHED = 4

    def __init__(self, status, extra_info=None):
        self._status = status  # should be one of the above
        self._extra_info = extra_info

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self._status == other._status
        if isinstance(other, int):
            return self._status == other
        return NotImplemented

    @property
    def extra_info(self):
        return self._extra_info

    @extra_info.setter
    def extra_info(self, value):
        self._extra_info = value

    @classmethod
    def not_started(cls, extra=None):
        return cls(cls.NOT_STARTED, extra)

    @classmethod
    def running(cls, extra=None):
        return cls(cls.RUNNING, extra)

    @classmethod
    def not_available(cls, extra=None):
        return cls(cls.STREAM_NOT_AVAILABLE, extra)

    @classmethod
    def finished(cls, extra=None):
        return cls(cls.FINISHED, extra)


class StreamRunner(QProcess):

    def __init__(self, stream: RegisteredStream, status=None, parent=None):
        super().__init__(parent)
        if status is None:
            status = SRStatus.not_started()
        self._status = status
        self._stream = stream
        self.setProgram("streamlink")
        self.setArguments([self._stream.full_URL, "best"])
        self.readyReadStandardOutput.connect(self.handle_stdout)
        self.finished.connect(self.ended)

    def run(self):
        print("trying to start stream...")
        self.start()
        self.waitForStarted(-1)
        self._status = SRStatus.running(self._status.extra_info)

    def handle_stdout(self):
        data = self.readAllStandardOutput().data()
        stdout = data.decode("utf8")
        if "error" in stdout:
            self._status = SRStatus.not_available(self._status.extra_info)

    def set_status(self, status):
        self._status = status

    def ended(self):
        if self._status == SRStatus.not_available():
            if self._status.extra_info is None:
                print("tried to start stream once, it failed")
                keep_trying = QPushButton("Keep Trying")
                err_dialog = ErrorDialog(
                    "Stream is unavailable",
                    NoStreamError(),
                    [(keep_trying, QDialogButtonBox.ButtonRole.AcceptRole)],
                    self.parent(),
                )
                keep_trying.clicked.connect(err_dialog.accept)
                if err_dialog.exec():
                    self.set_status(SRStatus.not_available(time.time() + 60))

            if self._status.extra_info is not None and time.time() >= self._status.extra_info:  # type: ignore
                print("tried starting stream for a while, it failed.")
                self._status = SRStatus.finished()
            else:
                self.run()
        else:
            self._status = SRStatus.finished()


class StreamButton(QPushButton):
    """GUI representation of a :class:`RegisteredStream` object.

    Args:
        stream (RegisteredStream): the object it represents.
        parent (QWidget | None): parent widget, optional. Defaults to None.
    """

    def __init__(self, stream: RegisteredStream, parent=None):

        super().__init__(stream.display_name, parent=parent)
        self._stream = stream
        self._runner = StreamRunner(stream, parent=self)
        self._pixmap = self._create_pixmap()
        self.clicked.connect(self.click_action)

    def paintEvent(self, event):  # type: ignore
        painter = QPainter(self)
        painter.drawPixmap(event.rect(), self._pixmap)

    def click_action(self):
        print("starting stream")
        self._runner.run()

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


class PlayStreamButton(QPushButton):

    def __init__(self, source, parent=None):
        super().__init__("Play", parent)
        self._source = source
        self.clicked.connect(self.click_action)

    def click_action(self):
        url = self._source.text()
        try:
            stream = RegisteredStream.from_url(url)
            # stream.start()
        except ParseError as err:
            ErrorDialog("Could not parse url", err, parent=self).exec()
        except NoStreamError as err:
            ErrorDialog("The stream is unavailable", err, parent=self).exec()


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
        self._layout.addWidget(add_stream_button, 0, 0)

        play_stream = QLineEdit()
        play_stream_button = PlayStreamButton(source=play_stream, parent=self)
        self._layout.addWidget(play_stream, 0, 1, 1, 3)
        self._layout.addWidget(play_stream_button, 0, 4)

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
