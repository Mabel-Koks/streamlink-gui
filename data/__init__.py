from abc import ABC, abstractmethod
from enum import Enum
from typing import NamedTuple, Self, Any
from pathlib import Path
import json
from subprocess import run, CalledProcessError

from .exceptions import ParseError, NoStreamError, UnsupportedError, ImpossibleError


def get_file_path(filename: str) -> Path:
    """Build the full file path from a filename.

    Args:
        filename (str): Name of the file to be found.

    Returns:
        Path: Full, absolute path to the file.
    """
    suffix = filename.split(".")[1]
    match suffix:
        case "png" | "jpg" | "jpeg" | "svg":
            fldr = "imgs"
        case "json" | "sql":
            fldr = "db"
        case _:
            fldr = "other"

    full_path = Path(__file__).parent / "files" / fldr / filename
    if not full_path.exists():
        raise FileNotFoundError(f"{filename} @ {full_path} does not exist.")
    return full_path


class Source(Enum):
    """Set of supported stream sources."""

    Twitch = "twitch"
    Youtube = "youtube"

    def URI_root(self) -> str:
        """Returns the base of the URL for the stream source.

        Returns:
            str: The base of the URL with a trailing slash.
        """
        match self:
            case Source.Twitch:
                return "twitch.tv/"
            case Source.Youtube:
                return "youtube.com/"
            case _:
                raise ImpossibleError(
                    f"encountered impossible value for source: `{self}`"
                )

    @classmethod
    def from_string(cls, str_val: str) -> Self:
        """Creates an Source value from a given string.

        Args:
            str_val (str): value to parse into a Source.

        Raises:
            UnsupportedError: The value does not match any of the enum values.

        Returns:
            Self: Instantiated Source.
        """
        for val in cls:
            if val.value == str_val.lower():
                return val
        raise UnsupportedError(
            f"Unsupported value for Source: `{str_val}`", (cls, str_val)
        )


class RegisteredStream(NamedTuple):
    """Collection of information required to both display and start a stream.

    Args:
        display_name (str): Pretty name for UI representation.
        source (Source): Stream source website.
        stream_name (str): ID of the streamer on `source`.
        icon (str, optional): Icon for UI representation, optional. Defaults to None.
    """

    display_name: str
    source: Source
    stream_name: str
    icon: str | None = None

    def start(self):
        """Start a stream using `streamlink`.

        Raises:
            NoStreamError: Stream failed to start.
        """
        try:
            run(
                [
                    "streamlink",
                    self.full_URI,
                    "best",
                ],
                check=True,
            )
        except CalledProcessError as err:
            # Maybe pass through more information.
            raise NoStreamError(
                f"Could not start stream for {self.display_name} @ {self.full_URI}",
                (self,),
            ) from None

    @property
    def full_URI(self):
        """The complete URL pointing to the stream source."""
        return self.source.URI_root() + self.stream_name

    @classmethod
    def from_config(cls, config: dict[str, str]) -> Self:
        """Create a RegisteredStream from a given config.

        The config must have the following fields:
            **source**: Source website of the stream, for supported values see :func:`Source`.
            **stream_name**: ID of the streamer on **source** website.

        See :class:`RegisteredStream` for all possible fields.

        Args:
            config (dict[str, str]): The config used to create the :class:`RegisteredStream`.

        Raises:
            ParseError: The config contained illegal values or was missing required values.

        Returns:
            Self: :class:`RegisteredStream` instance.
        """
        try:
            sname = config["stream_name"]
            dname = config.get("display_name", sname)
            source = Source.from_string(config["source"])
            icon = config.get("icon", None)
            return cls(display_name=dname, source=source, stream_name=sname, icon=icon)
        except (KeyError, UnsupportedError) as err:
            raise ParseError(
                f"Failed to parse config: {config}", (err.args[0], cls)
            ) from None

    @classmethod
    def from_url(cls, url, display_name=None, icon_path=None) -> Self:
        """Create a RegisteredStream from a given url.

        Args:
            url (str): Valid URL pointing to the stream.
            display_name (str, optional): Pretty name for UI representation. Defaults to None.
            icon_path (str, optional): Absolute path to icon for UI representation. Defaults to None.

        Raises:
            ParseError: The url did not resolve to a supported platform.

        Returns:
            Self: :class:`RegisteredStream` instance.
        """
        url = url.lower()
        result = {}
        match True:
            case _ if "twitch" in url:
                result["stream_name"] = url.split("/")[-1]
                result["source"] = "twitch"
            case _ if "youtube" in url:
                result["stream_name"] = url.split("@")[-1]
                result["source"] = "youtube"
            case _:
                raise ParseError(f"Could not parse url `{url}`", (url, cls))

        if icon_path is not None:
            dest = get_file_path(result["stream_name"] + ".png")
            Path(icon_path).rename(dest)
            result["icon"] = dest.name

        if display_name is None or display_name == "":
            result["display_name"] = result["stream_name"]
        else:
            result["display_name"] = display_name

        return cls.from_config(result)

    def as_config(self) -> dict[str, str]:
        """Creates a serializable config from the instance.

        Returns:
            dict[str, str]: Serializable config.
        """
        dct = {"stream_name": self.stream_name, "source": self.source.value}
        if self.display_name != self.stream_name:
            dct["display_name"] = self.display_name
        if self.icon is not None:
            dct["icon"] = self.icon
        return dct

    def get_icon_path(self) -> str | None:
        if self.icon is not None:
            return str(get_file_path(self.icon))
        return None

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return NotImplemented

        return self.full_URI == other.full_URI


class Connection(ABC):
    """Abstract connection class, streamlink-gui assumes all connections subclass this."""

    @abstractmethod
    def __init__(self, entrypoint: Any):
        """Creates the connection from :param:`entrypoint`.

        Args:
            entrypoint (Any): Information required for the connection to be established.
        """

    @abstractmethod
    def get_streams(self) -> list[RegisteredStream]:
        """Retrieves all registered stream objects.

        Returns:
            list[RegisteredStream]: The registered stream objects.
        """

    @abstractmethod
    def add_stream(self, stream: RegisteredStream):
        """Registers a new stream to the connection endpoint.

        Args:
            stream (RegisteredStream): stream to be registered.
        """

    @abstractmethod
    def finish(self) -> None:
        """Final action of the connection, connection might be closed afterwards."""


class JSONConnection(Connection):
    """Connection to a JSON file containing all required information.

    Args:
            entrypoint (Path): Path to the JSON file.
    """

    def __init__(self, entrypoint: Path):
        with entrypoint.open("r") as f:
            lst = json.load(f)
        self._sourcepath = entrypoint
        self._streams = self._parse_dct(lst)

    def _parse_dct(self, lst: list[dict[str, str]]) -> list[RegisteredStream]:
        streams = []
        for entry in lst:
            try:
                stream = RegisteredStream.from_config(entry)
                streams.append(stream)
            except ParseError as err:
                pass  # TODO: create failure logging, inform user of parsing failure.
        return streams

    def get_streams(self) -> list[RegisteredStream]:
        return self._streams

    def add_stream(self, stream):
        if stream not in self._streams:
            self._streams.append(stream)

    def finish(self):
        with self._sourcepath.open("w") as f:
            json.dump([stream.as_config() for stream in self._streams], f, indent=4)
