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
    QAbstractButton,
)
from PyQt6.QtGui import QPixmap, QPainter, QColor, QPen
from PyQt6.QtCore import Qt, QProcess, QThread, pyqtSignal
from .data import RegisteredStream, Connection
from .data.exceptions import NoStreamError, ParseError


class LogDialog(QDialog):
    """Dialog displaying an error log in a text field.

    Args:
        error (Exception): The error to display.
        parent (QWidget, optional): Parent object. Defaults to None.
    """

    def __init__(self, error: Exception, parent: QWidget | None = None):
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

    def __init__(
        self,
        error_message: str,
        error: Exception,
        extra_buttons: list[tuple[QAbstractButton, QDialogButtonBox.ButtonRole]] = [],
        parent: QWidget | None = None,
    ):
        """Dialog displaying an error message, with buttons for error logs and optional
        extra buttons for extra functionality.

        Args:
            error_message (str): The message to display.
            error (Exception): The exception source of the error.
            extra_buttons (list[tuple[QAbstractButton, QDialogButtonBox.ButtonRole]], optional):
                List of extra buttons and their roles. Defaults to [].
            parent (QWidget | None, optional): Parent object. Defaults to None.
        """
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
        self.buttonBox.accepted.connect(self._parse_response)
        self.buttonBox.rejected.connect(self.reject)
        layout.addWidget(self.buttonBox, 4, 0, 1, 3)
        self.setLayout(layout)

    def _parse_response(self):
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

    def __init__(self, button_text: str, parent: QWidget | None = None):
        super().__init__(button_text, parent=parent)
        self.clicked.connect(self._click_action)
        self._file = None

    def _click_action(self):
        file_dialog = QFileDialog()
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        file_dialog.setNameFilter("Images (*.png *.jpg)")
        if file_dialog.exec():
            self._file = file_dialog.selectedFiles()[0]


class NewStreamButton(QPushButton):
    """Button that creates a dialog for registering a new stream.

    Args:
        connection (Connection): connection to the data, to register the new stream to.
        update_fn (Callable): function called when a new stream has successfully been registered.
        parent (QWidget | None): parent widget, optional. Defaults to None.
    """

    def __init__(self, connection, update_fn, parent=None):
        super().__init__("Add Stream!", parent=parent)
        self._connection = connection
        self._update_fn = update_fn
        self.clicked.connect(self._click_action)

    def _click_action(self):
        dialog_box = NewStreamDialog(self._connection, self.parent())
        if dialog_box.exec():
            self._update_fn()


class StreamRunner(QThread):
    """Runs the stream starting process in a separate thread.

    Start the runner using :func:`start()`. This will call the right methods.

    Args:
        stream (RegisteredStream): The stream to start.
        wait (int): Time to wait inbetween tries.
    """

    # streamrunner states, these are communicated over the stream_status signal.
    STARTING = 0
    RUNNING = 1
    NO_STREAM = 2
    FINISHED = 3

    stream_status = pyqtSignal(int)

    def __init__(self, stream: RegisteredStream, wait: int = 60):
        super().__init__()
        self._stream = stream
        self._process = None
        self._stop = False
        self._start_time = time.time()
        self._wait = wait

    def run(self):
        """Sets up the process and keeps trying until :func:`stop()` is called.

        Don't call this directly or it'll block the thread. Call :func:`start()`
        instead, which will run this in a new thread.
        """
        self._stop = False
        self._start_time = time.time()
        self.stream_status.emit(StreamRunner.STARTING)
        self._process = QProcess()
        self._process.setProgram("streamlink")
        self._process.setArguments([self._stream.full_URL, "best"])
        while not self._stop:
            self._process.start()
            self.stream_status.emit(StreamRunner.RUNNING)
            self._process.waitForFinished(-1)
            data = self._process.readAllStandardOutput().data().decode()
            if "error" in data:
                self.stream_status.emit(StreamRunner.NO_STREAM)
            elif "Starting player" in data:
                self.stream_status.emit(StreamRunner.FINISHED)
                self.stop()
            time.sleep(self._wait)  # don't *immediately* retry
        self.stream_status.emit(StreamRunner.FINISHED)

    def stop(self):
        """Signal the thread to stop trying to start the stream."""
        self._stop = True

    @property
    def start_time(self):
        """Timestamp when the process was started."""
        return self._start_time


class StopRunnerDialog(QDialog):
    """Dialog that shows for how long the StreamRunner will keep retrying
    and allows to abort the StreamRunner process.

    Args:
        runner (StreamRunner): The StreamRunner trying to start a stream.
        time_to_try (int | float): Seconds left to try.
        parent (QWidget | None, optional): Parent widget. Defaults to None.
    """

    def __init__(
        self,
        runner: StreamRunner,
        time_to_try: int | float,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._runner = runner
        self._time_left = int(time_to_try / 60)
        self._text_template = "Retrying for another {} minute{}..."

        self.setWindowTitle("Abort?")

        layout = QVBoxLayout()
        self._text = QLabel(
            self._text_template.format(
                self._time_left, "s" if self._time_left > 1 else ""
            )
        )
        layout.addWidget(self._text)

        buttonbox = QDialogButtonBox(QDialogButtonBox.StandardButton.Abort)
        buttonbox.rejected.connect(self._abort)
        layout.addWidget(buttonbox)

        self.setLayout(layout)

    def _abort(self):
        self._runner.stop()
        self.reject()

    def set_time(self, value):
        """Update the time left to try."""
        self._time_left = int(value / 60)
        self._text.setText(
            self._text_template.format(
                self._time_left, "s" if self._time_left > 1 else ""
            )
        )

    def end_dialog(self):
        """Forcibly close the dialog."""
        self.reject()


class StreamButton(QPushButton):
    """GUI representation of a :class:`RegisteredStream` object.

    Args:
        stream (RegisteredStream): the object it represents.
        parent (QWidget | None): parent widget, optional. Defaults to None.
    """

    def __init__(self, stream: RegisteredStream, parent=None):

        super().__init__(stream.display_name, parent=parent)
        self._timeout = 3600
        self._run_status = 0
        self._stream = stream
        self._runner = StreamRunner(stream)
        self._runner.stream_status.connect(self._stream_handler)
        self._pixmap = self._create_pixmap()
        self.clicked.connect(self.click_action)

    def _stream_handler(self, value):
        print(value)
        now = time.time()
        match value:
            case StreamRunner.STARTING:
                self._run_status = 0
            case StreamRunner.NO_STREAM:
                try_until = self._runner.start_time + self._timeout
                if self._run_status == 0:
                    self._run_status = StopRunnerDialog(
                        self._runner, try_until - now, parent=self
                    )
                    self._run_status.exec()
                if try_until <= now:
                    if isinstance(self._run_status, StopRunnerDialog):
                        self._run_status.end_dialog()
                    self._runner.stop()
                    err_msg = f"Failed to start stream after {self._timeout} seconds"
                    ErrorDialog(
                        err_msg,
                        NoStreamError(err_msg, (self._stream,)),
                        parent=self,
                    ).exec()
                else:
                    if isinstance(self._run_status, StopRunnerDialog):
                        self._run_status.set_time(try_until - now)
            case StreamRunner.FINISHED:
                if isinstance(self._run_status, StopRunnerDialog):
                    self._run_status.end_dialog()
                self._run_status = 0

    def paintEvent(self, event):  # type: ignore
        painter = QPainter(self)
        painter.drawPixmap(event.rect(), self._pixmap)

    def click_action(self):
        self._runner.start()

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
