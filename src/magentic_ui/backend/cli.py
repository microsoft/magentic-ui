import os
import warnings
import typer
import uvicorn
from typing_extensions import Annotated
from typing import Optional
from pathlib import Path
import logging

from ..version import VERSION

# Configure basic logging to show only errors
logging.basicConfig(level=logging.ERROR)

# Create a Typer application instance with a descriptive help message
# This is the main entry point for CLI commands
app = typer.Typer(help="MagenticLite: A human-centered interface for web agents.")

# Ignore deprecation warnings from websockets
warnings.filterwarnings("ignore", message="websockets.legacy is deprecated*")
warnings.filterwarnings(
    "ignore", message="websockets.server.WebSocketServerProtocol is deprecated*"
)

# Ignore warnings about ffmpeg or avconv not being found
# Audio is not used in the UI, so we can ignore this warning
warnings.filterwarnings("ignore", message="Couldn't find ffmpeg or avconv*")


def get_env_file_path():
    """
    Create a temporary environment file path in the user's home directory.
    Used to pass environment variables to Uvicorn workers.

    Returns:
        str: The full path to the temporary environment file
    """
    app_dir = os.path.join(os.path.expanduser("~"), ".magentic_ui")
    if not os.path.exists(app_dir):
        os.makedirs(app_dir, exist_ok=True)
    return os.path.join(app_dir, "temp_env_vars.env")


# This decorator makes this function the default action when no subcommand is provided
# invoke_without_command=True means this function runs automatically when only 'magentic-ui' is typed
@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,  # Typer context provides information about the command invocation
    host: str = typer.Option("127.0.0.1", help="Host to run the UI on."),
    port: int = typer.Option(8081, help="Port to run the UI on."),
    reload: Annotated[
        bool, typer.Option("--reload", help="Reload the UI on code changes.")
    ] = False,
    docs: bool = typer.Option(True, help="Whether to generate API docs."),
    appdir: str = typer.Option(
        str(Path.home() / ".magentic_ui"),
        help="Path to the app directory where files are stored.",
    ),
    database_uri: Optional[str] = typer.Option(
        None, "--database-uri", help="Database URI to connect to."
    ),
    upgrade_database: bool = typer.Option(
        False, "--upgrade-database", help="Upgrade the database schema on startup."
    ),
    config: Optional[str] = typer.Option(
        None, "--config", help="Path to the config file."
    ),
    version: bool = typer.Option(
        False, "--version", help="Print the version of MagenticLite and exit."
    ),
    fara_agent: Annotated[
        bool,
        typer.Option(
            "--fara",
            help="Launch the UI with the FARA-based web surfer agent instead of the default GPT-oriented surfer.",
        ),
    ] = False,
    reset_config: bool = typer.Option(
        False,
        "--reset-config",
        help="Clear saved model config so onboarding runs again.",
    ),
):
    """
    MagenticLite: A human-centered interface for web agents.

    Run `magentic-ui` to start the application.
    """
    # Check if version flag was provided
    if version:
        typer.echo(f"MagenticLite version: {VERSION}")
        raise typer.Exit()

    # This conditional checks if a subcommand was provided
    # If no subcommand was specified (e.g., just 'magentic-ui'), run the UI
    if ctx.invoked_subcommand is None:
        run_ui(
            host=host,
            port=port,
            reload=reload,
            docs=docs,
            appdir=appdir,
            database_uri=database_uri,
            upgrade_database=upgrade_database,
            config=config,
            fara_agent=fara_agent,
            reset_config=reset_config,
        )


def run_ui(
    host: str,
    port: int,
    reload: bool,
    docs: bool,
    appdir: str,
    database_uri: Optional[str],
    upgrade_database: bool,
    config: Optional[str],
    fara_agent: bool,
    reset_config: bool = False,
):
    """
    Core logic to run the Magentic-UI web application.
    """
    # Display a green, bold "Starting MagenticLite" message
    typer.echo(typer.style("Starting MagenticLite", fg=typer.colors.GREEN, bold=True))

    typer.echo("Launching Web Application...")

    # === Environment Setup ===
    # Create environment variables to pass to the web application
    env_vars = {
        "_HOST": host,
        "_PORT": port,
        "_API_DOCS": str(docs),
    }

    # Add optional environment variables
    if appdir:
        env_vars["_APPDIR"] = appdir
    if database_uri:
        env_vars["DATABASE_URI"] = database_uri
    if upgrade_database:
        env_vars["_UPGRADE_DATABASE"] = "1"

    env_vars["FARA_AGENT"] = str(fara_agent)

    if reset_config:
        env_vars["_RESET_CONFIG"] = "1"

    # Handle configuration file path
    if not config:
        # Look for config.yaml in the current directory if not specified
        if os.path.isfile("config.yaml"):
            config = "config.yaml"
        else:
            typer.echo("Config file not provided. Using default settings.")
    if config:
        env_vars["_CONFIG"] = config

    # Create a temporary environment file to share with the Uvicorn process.
    # Magentic-UI runs single-process (WS connections, sandbox manager, and
    # session token all live in per-process memory).
    env_file_path = get_env_file_path()
    with open(env_file_path, "w") as temp_env:
        for key, value in env_vars.items():
            temp_env.write(f"{key}={value}\n")

    # Start the Uvicorn server with the configured settings
    uvicorn.run(
        "magentic_ui.backend.web.app:app",  # Path to the ASGI application
        host=host,
        port=port,
        reload=reload,
        reload_excludes=["**/alembic/*", "**/alembic.ini", "**/versions/*"]
        if reload
        else None,
        env_file=env_file_path,  # Pass environment variables via file
    )


# This command is hidden from help to encourage using the new syntax
# but kept for backward compatibility with existing scripts and documentation
@app.command(hidden=True)
def ui(
    host: str = "127.0.0.1",
    port: int = 8081,
    reload: Annotated[bool, typer.Option("--reload")] = False,
    docs: bool = True,
    appdir: str = str(Path.home() / ".magentic_ui"),
    database_uri: Optional[str] = None,
    upgrade_database: bool = False,
    config: Optional[str] = None,
    fara_agent: Annotated[
        bool,
        typer.Option(
            "--fara",
            help="Launch the UI with the FARA-based web surfer agent instead of the default GPT-oriented surfer.",
        ),
    ] = False,
):
    """
    [Deprecated] Run MagenticLite.
    This command is kept for backward compatibility.
    """
    run_ui(
        host=host,
        port=port,
        reload=reload,
        docs=docs,
        appdir=appdir,
        database_uri=database_uri,
        upgrade_database=upgrade_database,
        config=config,
        fara_agent=fara_agent,
    )


# Keep the version command for backward compatibility but hide it from help
@app.command(hidden=True)
def version():
    """
    Print the version of the MagenticLite backend CLI.
    """
    typer.echo(f"MagenticLite version: {VERSION}")


@app.command(hidden=True)
def help():
    """
    Show help information about available commands and options.
    """
    # Use a system call to run the command with --help
    import subprocess
    import sys
    import os

    # Get the command that was used to run this script
    command = os.path.basename(sys.argv[0])

    # If running directly as a module, use the appropriate command name
    if command == "python" or command == "python3":
        command = "magentic-ui"

    # Run the command with --help
    try:
        subprocess.run([command, "--help"])
    except FileNotFoundError:
        # Fallback if the command isn't found in PATH
        typer.echo(f"Error: Command '{command}' not found in PATH.")
        typer.echo(f"For more information, run `{command} --help`")


def run():
    """
    Main entry point called by the 'magentic' and 'magentic-ui' commands.
    This function is referenced in pyproject.toml's [project.scripts] section.
    """
    app()  # Hand control to the Typer application


if __name__ == "__main__":
    app()  # Allow running this file directly with 'python -m magentic_ui.backend.cli'
