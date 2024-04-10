import io
import logging
import os
import subprocess
import traceback

from PIL import Image
from cairosvg import svg2png  # type: ignore
from functools import wraps
from pathlib import Path
from typing import Callable, Optional, ParamSpec, TypeVar


class suppress_stdout_stderr(object):
    # https://stackoverflow.com/questions/11130156/suppress-stdout-stderr-print-from-python-functions
    """
    A context manager for doing a "deep suppression" of stdout and stderr in
    Python, i.e. will suppress all print, even if the print originates in a
    compiled C/Fortran sub-function.
       This will not suppress raised exceptions, since exceptions are printed
    to stderr just before a script exits, and after the context manager has
    exited (at least, I think that is why it lets exceptions through).

    """

    def __init__(self) -> None:
        # Open a pair of null files
        self.null_fds = [os.open(os.devnull, os.O_RDWR) for x in range(2)]
        # Save the actual stdout (1) and stderr (2) file descriptors.
        self.save_fds = [os.dup(1), os.dup(2)]

    def __enter__(self) -> None:
        # Assign the null pointers to stdout and stderr.
        os.dup2(self.null_fds[0], 1)
        os.dup2(self.null_fds[1], 2)

    def __exit__(self) -> None:
        # Re-assign the real stdout/stderr back to (1) and (2)
        os.dup2(self.save_fds[0], 1)
        os.dup2(self.save_fds[1], 2)
        # Close all file descriptors
        for fd in self.null_fds + self.save_fds:
            os.close(fd)


class ParseError(Exception):
    pass


class ExternalError(Exception):
    pass


def get_application_output(
    command: str, shell: bool = False, timeout: Optional[float] = None
) -> str:
    """Run a command and get the output.

    Args:
        command (str, list): The command to run
        and it's arguments.
        shell (bool), optional: True if executing on
        shell, else False. Default is False.
        timeout (int, None), optional: Set a max
        execution time in seconds for the command.

    Returns:
        str: Command output if the command ran with
        a zero exit code. Returns a string containing
        the error reason in case the command failed.
    """
    try:
        return subprocess.run(
            command,
            shell=shell,
            check=True,
            universal_newlines=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=timeout,
        ).stdout
    except subprocess.CalledProcessError:
        return "invalid"
    except subprocess.TimeoutExpired:
        return "timeout"
    except FileNotFoundError:
        return "unavailable"


def image_has_transparency(img: Image.Image) -> bool:
    if img.info.get("transparency", None) is not None:
        return True
    if img.mode == "P":
        transparent = img.info.get("transparency", -1)
        for _, index in img.getcolors():
            if index == transparent:
                return True
    elif img.mode == "RGBA":
        extrema = img.getextrema()
        if len(extrema) >= 3 and extrema[3][0] < 255:
            return True

    return False


def load_image_as_png(
    path: Path, dpi: int
) -> tuple[Image.Image, bytes, tuple[int, int]]:
    logging.debug(f"Loading image {path} as PNG...")
    if path.suffix == ".svg":
        img_bytes = svg2png(url=str(path), dpi=dpi)
        assert isinstance(img_bytes, bytes)
        img = Image.open(io.BytesIO(img_bytes))
    else:
        img = Image.open(path)
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        img_bytes = img_bytes.getvalue()
    canvas_size = (img.size[0], img.size[1])
    return img, img_bytes, canvas_size


GenericReturn = TypeVar("GenericReturn")
GenericParams = ParamSpec("GenericParams")


def with_exception_trace(
    f: Callable[GenericParams, GenericReturn]
) -> Callable[GenericParams, GenericReturn]:
    @wraps(f)
    def wrapped_f(
        *args: GenericParams.args, **kwargs: GenericParams.kwargs
    ) -> GenericReturn:
        try:
            return f(*args, **kwargs)
        except:
            traceback.print_exc()
            raise

    return wrapped_f
