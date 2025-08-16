import os
import stat
import sys
import tarfile
from typing import Annotated, Optional

from myai.__about__ import __version__
from myai.commands import setup_cli
import rich
import typer

app = typer.Typer()
console = rich.console.Console()


@app.callback(invoke_without_command=True)
def callback(ctx: typer.Context):
    """
    Interact with MyAI with this command.

    See the Commands section for the supported commands.
    """
    # Check if the callback was triggered by the primary app.
    if ctx.invoked_subcommand is None:
        # If no subcommand was invoked, execute the app's --help menu.
        ctx.invoke(app, ["--help"])


@app.command()
def version():
    print(__version__)


def main():
    app.add_typer(setup_cli.app, name="setup")
    app()


if __name__ == "__main__":
    main()
