"""
MyAI Setup CLI command interface.
"""

from enum import Enum

import typer

app = typer.Typer()


class Outputs(str, Enum):
    pretty = "pretty"
    json = "json"


########################################################################################
# The callback function's docstring is used by typer to derive the CLI menu            #
# information, and provides a default command landing point when no command is passed. #
#                                                                                      #
# Ie..simply passing `bt okta` won't yield an error, but will yield                   #
# the `bt --help` page instead.                                                       #
########################################################################################
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


# Subcommand docstrings are used for help messages
@app.command()
def all_setup():
    """
    Setup MyAI.

    Examples:
      myai setup all
    """
    pass


@app.command()
def global_setup():
    """
    Setup global MyAI configuration.

    Examples:
      myai setup global-setup
    """
    pass


@app.command()
def project():
    """
    Setup project MyAI configuration.

    Examples:
      myai setup project
    """
    pass


@app.command()
def client(client_name: str):
    """
    Setup client-specific configuration.

    Args:
        client_name: The client name (e.g., claude, cursor)

    Examples:
      myai setup client claude
    """
    # TODO: Implement client-specific setup logic in Phase 5
    _ = client_name  # Acknowledge parameter usage
    pass
