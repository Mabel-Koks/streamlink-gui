from PyQt6.QtWidgets import QMainWindow, QPushButton, QVBoxLayout, QWidget
from .data import RegisteredStream, Connection


class StreamButton(QPushButton):

    def __init__(self, stream: RegisteredStream):
        super().__init__(stream.display_name)
        self._stream = stream
        self.clicked.connect(self.click_action)

    def click_action(self):
        print(self._stream.full_URI)


class MainWindow(QMainWindow):
    def __init__(self, connection: Connection):
        super().__init__()

        self.setWindowTitle("My App")
        layout = QVBoxLayout()
        container = QWidget()

        streams = connection.get_streams()
        for stream in streams:
            button = StreamButton(stream)
            layout.addWidget(button)

        container.setLayout(layout)
        self.setCentralWidget(container)
