from abc import ABC, abstractmethod
from enum import Enum
from typing import NamedTuple, Self, Any
from pathlib import Path
import json
from subprocess import run


class Source(Enum):
    Twitch = "twitch"
    Youtube = "youtube"

    def URI_root(self) -> str:
        match self:
            case Source.Twitch:
                return "twitch.tv/"
            case Source.Youtube:
                return "youtube.com/"
            case _:
                raise ValueError(f"encountered impossible value for self: `{self}`")

    @classmethod
    def from_string(cls, str_val: str) -> Self:
        for val in cls:
            if val.value == str_val.lower():
                return val
        raise ValueError(f"Unsupported value for Source: `{str_val}`")


class RegisteredStream(NamedTuple):
    display_name: str
    source: Source
    stream_name: str
    icon: str | None = None

    def start(self):
        try:
            run(
                [
                    "streamlink",
                    self.full_URI,
                    "best",
                ]
            )
        except Exception as e:
            pass  # TODO: add custom exception so we can handle it in the gui

    @property
    def full_URI(self):
        return self.source.URI_root() + self.stream_name

    @classmethod
    def from_config(cls, config: dict[str, str]) -> Self:
        sname = config["stream_name"]
        dname = config.get("display_name", sname)
        source = Source.from_string(config["source"])
        icon = config.get("icon", None)
        return cls(display_name=dname, source=source, stream_name=sname, icon=icon)

    @classmethod
    def from_url(cls, url, display_name=None, icon_path=None):
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
                raise ValueError(f"Could not parse url `{url}`")

        if icon_path is not None:
            dest = Path(__file__).parent / (result["stream_name"] + ".png")
            Path(icon_path).rename(dest)
            result["icon"] = dest.name

        if display_name is not None:
            result["display_name"] = display_name

        return cls.from_config(result)

    def as_config(self) -> dict[str, str]:
        dct = {"stream_name": self.stream_name, "source": self.source.value}
        if self.display_name != self.stream_name:
            dct["display_name"] = self.display_name
        if self.icon is not None:
            dct["icon"] = self.icon
        return dct

    def get_icon_path(self) -> str | None:
        if self.icon is not None:
            return str(Path(__file__).parent / self.icon)
        return None


class Connection(ABC):

    @abstractmethod
    def __init__(self, entrypoint: Any):
        pass

    @abstractmethod
    def get_streams(self) -> list[RegisteredStream]:
        pass

    @abstractmethod
    def add_stream(self, stream: RegisteredStream):
        pass

    @abstractmethod
    def finish(self) -> None:
        pass


class JSONConnection(Connection):

    def __init__(self, entrypoint: Path):
        with entrypoint.open("r") as f:
            lst = json.load(f)
        self._sourcepath = entrypoint
        self._streams = self._parse_dct(lst)

    def _parse_dct(self, lst: list[dict[str, str]]) -> list[RegisteredStream]:
        return [RegisteredStream.from_config(entry) for entry in lst]

    def get_streams(self):
        return self._streams

    def add_stream(self, stream):
        if stream not in self._streams:
            self._streams.append(stream)

    def finish(self):
        with self._sourcepath.open("w") as f:
            json.dump([stream.as_config() for stream in self._streams], f)


def default_icon():
    return str(Path(__file__).parent / "default_icon.png")
