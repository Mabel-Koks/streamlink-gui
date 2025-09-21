from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import Any, NamedTuple, Self
from pathlib import Path

import json


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

    @property
    def full_URI(self):
        return self.source.URI_root() + self.stream_name

    @classmethod
    def from_config(cls, config: dict[str, str]) -> Self:
        sname = config["stream_name"]
        dname = config.get("display_name", sname)
        source = Source.from_string(config["source"])
        return cls(display_name=dname, source=source, stream_name=sname)

    def as_config(self) -> dict[str, str]:
        dct = {"stream_name": self.stream_name, "source": self.source.value}
        if self.display_name != self.stream_name:
            dct["display_name"] = self.display_name
        return dct


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
