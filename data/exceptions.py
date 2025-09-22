class ParseError(ValueError):
    """Raised when parsing an object failed.

    Used when an object should be created from a config but it failed due to
    missing or unsupported values. Unlike an UnsupportedError, this exception is
    only raised when object creation fails.

    Args:
        value: the source that caused the failure.
        object: the object that failed to create due to the error.
    """


class NoStreamError(ValueError):
    """No stream has been found.

    Used when trying to start a stream has failed due to none being available.

    Args:
        stream (RegisteredStream): stream object trying to start the stream.
    """


class UnsupportedError(ValueError):
    """Raised when an unsupported value is encountered.

    Used when a specific (set of) value(s) is expected, but a different one
    is encountered. Similar to a ParseError, but unlike a ParseError only raised
    for single value errors.

    Args:
        value: the unsupported value.
        source: object that raised the error.
    """


class ImpossibleError(Exception):
    """Code is in an impossible to reach state.

    The most common use-case is in the final catch-all guard of a match statement.
    When this error is raised, that always means the code contains a bug. This is
    essentially a debug statement.
    """
