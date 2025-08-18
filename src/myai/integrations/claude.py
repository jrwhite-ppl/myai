"""
Claude Code integration adapter.

This module provides integration with Claude Code (claude-code),
allowing MyAI to sync agents and configurations with Claude's desktop application.
"""

import json
import os
import platform
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from myai.integrations.base import (
    AbstractAdapter,
    AdapterCapability,
    AdapterConfigError,
    AdapterInfo,
    AdapterStatus,
)


class ClaudeAdapter(AbstractAdapter):
    """Adapter for Claude Code integration."""

    def __init__(self, name: str = "claude", config: Optional[Dict[str, Any]] = None):
        super().__init__(name, config)
        self._config_paths = self._detect_config_paths()
        self._installation_path: Optional[Path] = None
        self._version: Optional[str] = None

    @property
    def info(self) -> AdapterInfo:
        """Get adapter information."""
        if not self._info:
            self._info = AdapterInfo(
                name=self.name,
                display_name="Claude Code",
                description="Integration with Claude Code desktop application",
                version="1.0.0",
                tool_name="Claude Code",
                tool_version=self._version,
                capabilities={
                    AdapterCapability.READ_CONFIG,
                    AdapterCapability.WRITE_CONFIG,
                    AdapterCapability.SYNC_AGENTS,
                    AdapterCapability.DETECT_CHANGES,
                    AdapterCapability.BACKUP_RESTORE,
                    AdapterCapability.VALIDATION,
                    AdapterCapability.MIGRATION,
                },
                status=AdapterStatus.UNKNOWN,
                config_path=self._get_primary_config_path(),
                installation_path=self._installation_path,
            )
        return self._info

    def _detect_config_paths(self) -> List[Path]:
        """Detect possible Claude configuration paths."""
        system = platform.system()
        paths = []

        if system == "Darwin":  # macOS
            home = Path.home()
            paths.extend(
                [
                    home / "Library" / "Application Support" / "Claude",
                    home / ".config" / "claude",
                    home / ".claude",
                ]
            )
        elif system == "Windows":
            appdata = os.getenv("APPDATA")
            if appdata:
                paths.extend(
                    [
                        Path(appdata) / "Claude",
                        Path(appdata) / "Anthropic" / "Claude",
                    ]
                )

            home = Path.home()
            paths.extend(
                [
                    home / ".config" / "claude",
                    home / ".claude",
                ]
            )
        else:  # Linux and others
            home = Path.home()
            paths.extend(
                [
                    home / ".config" / "claude",
                    home / ".local" / "share" / "claude",
                    home / ".claude",
                    Path("/etc/claude"),
                ]
            )

        return [path for path in paths if path.exists()]

    def _get_primary_config_path(self) -> Optional[Path]:
        """Get the primary configuration path."""
        if self._config_paths:
            return self._config_paths[0]
        return None

    def _detect_installation_paths(self) -> List[Path]:
        """Detect possible Claude installation paths."""
        system = platform.system()
        paths = []

        if system == "Darwin":  # macOS
            paths.extend(
                [
                    Path("/Applications/Claude.app"),
                    Path("/Applications/Claude Code.app"),
                    Path("/usr/local/bin/claude"),
                    Path("/opt/homebrew/bin/claude"),
                ]
            )
        elif system == "Windows":
            program_files = os.getenv("PROGRAMFILES")
            program_files_x86 = os.getenv("PROGRAMFILES(X86)")

            if program_files:
                paths.extend(
                    [
                        Path(program_files) / "Claude",
                        Path(program_files) / "Claude Code",
                        Path(program_files) / "Anthropic" / "Claude",
                    ]
                )

            if program_files_x86:
                paths.extend(
                    [
                        Path(program_files_x86) / "Claude",
                        Path(program_files_x86) / "Claude Code",
                        Path(program_files_x86) / "Anthropic" / "Claude",
                    ]
                )
        else:  # Linux and others
            paths.extend(
                [
                    Path("/usr/bin/claude"),
                    Path("/usr/local/bin/claude"),
                    Path("/opt/claude/bin/claude"),
                    Path.home() / ".local" / "bin" / "claude",
                ]
            )

        return [path for path in paths if path.exists()]

    async def initialize(self) -> bool:
        """Initialize the Claude adapter."""
        try:
            # Detect installation
            if not await self.detect_installation():
                if not self._info:
                    self._info = self.info
                self._info.status = AdapterStatus.ERROR
                self._info.error_message = "Claude Code not found"
                return False

            # Try to get version information
            self._version = await self.get_version_info()

            # Check configuration
            if not self._info:
                self._info = self.info
            config_path = self._get_primary_config_path()
            if config_path:
                self._info.status = AdapterStatus.CONFIGURED
            else:
                self._info.status = AdapterStatus.AVAILABLE

            self._initialized = True
            return True

        except Exception as e:
            if not self._info:
                self._info = self.info
            self._info.status = AdapterStatus.ERROR
            self._info.error_message = str(e)
            return False

    async def detect_installation(self) -> bool:
        """Detect if Claude Code is installed."""
        # Check for executable
        installation_paths = self._detect_installation_paths()

        for path in installation_paths:
            if path.exists():
                self._installation_path = path
                return True

        # Try to run claude command
        try:
            result = subprocess.run(
                ["claude", "--version"], capture_output=True, text=True, timeout=5, check=False  # noqa: S607,S603
            )
            if result.returncode == 0:
                return True
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return False

    async def get_status(self) -> AdapterStatus:
        """Get current adapter status."""
        if not self._initialized:
            return AdapterStatus.UNKNOWN

        if not await self.detect_installation():
            return AdapterStatus.ERROR

        config_path = self._get_primary_config_path()
        if config_path and (config_path / "settings.json").exists():
            return AdapterStatus.CONFIGURED

        return AdapterStatus.AVAILABLE

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check."""
        health: Dict[str, Any] = {
            "status": "healthy",
            "timestamp": None,
            "checks": {},
            "errors": [],
            "warnings": [],
        }

        try:
            # Check installation
            is_installed = await self.detect_installation()
            health["checks"]["installation"] = {
                "status": "pass" if is_installed else "fail",
                "message": f"Claude Code {'found' if is_installed else 'not found'}",
            }

            if not is_installed:
                health["status"] = "unhealthy"
                health["errors"].append("Claude Code installation not detected")
                return health

            # Check configuration
            config_path = self._get_primary_config_path()
            health["checks"]["configuration"] = {
                "status": "pass" if config_path else "fail",
                "message": f"Configuration {'found' if config_path else 'not found'}",
                "path": str(config_path) if config_path else None,
            }

            if config_path:
                # Check if settings file exists
                settings_file = config_path / "settings.json"
                health["checks"]["settings"] = {
                    "status": "pass" if settings_file.exists() else "warning",
                    "message": f"Settings file {'exists' if settings_file.exists() else 'not found'}",
                    "path": str(settings_file),
                }

                if not settings_file.exists():
                    health["warnings"].append("Claude settings file not found")

            # Check version
            version = await self.get_version_info()
            health["checks"]["version"] = {
                "status": "pass" if version else "warning",
                "message": f"Version: {version or 'unknown'}",
            }

            if not version:
                health["warnings"].append("Could not determine Claude version")

        except Exception as e:
            health["status"] = "unhealthy"
            health["errors"].append(f"Health check failed: {e}")

        from datetime import datetime, timezone

        health["timestamp"] = datetime.now(timezone.utc).isoformat()

        return health

    async def get_configuration(self) -> Dict[str, Any]:
        """Get Claude configuration."""
        config_path = self._get_primary_config_path()
        if not config_path:
            msg = "Claude configuration path not found"
            raise AdapterConfigError(msg, self.name)

        settings_file = config_path / "settings.json"
        if not settings_file.exists():
            return {}

        try:
            with open(settings_file, encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            msg = f"Invalid JSON in settings file: {e}"
            raise AdapterConfigError(msg, self.name) from e
        except Exception as e:
            msg = f"Failed to read settings: {e}"
            raise AdapterConfigError(msg, self.name) from e

    async def set_configuration(self, config: Dict[str, Any]) -> bool:
        """Set Claude configuration."""
        config_path = self._get_primary_config_path()
        if not config_path:
            msg = "Claude configuration path not found"
            raise AdapterConfigError(msg, self.name)

        # Ensure config directory exists
        config_path.mkdir(parents=True, exist_ok=True)

        settings_file = config_path / "settings.json"

        try:
            # Merge with existing config if it exists
            existing_config = {}
            if settings_file.exists():
                with open(settings_file, encoding="utf-8") as f:
                    existing_config = json.load(f)

            # Merge configurations
            merged_config = {**existing_config, **config}

            # Write back to file
            with open(settings_file, "w", encoding="utf-8") as f:
                json.dump(merged_config, f, indent=2, ensure_ascii=False)

            return True

        except Exception as e:
            msg = f"Failed to write settings: {e}"
            raise AdapterConfigError(msg, self.name) from e

    async def sync_agents(self, agents: List[Any], *, dry_run: bool = False) -> Dict[str, Any]:
        """Sync agents to Claude Code."""
        result = {
            "status": "success",
            "synced": 0,
            "skipped": 0,
            "errors": [],
            "warnings": [],
            "dry_run": dry_run,
        }

        config_path = self._get_primary_config_path()
        if not config_path:
            result["status"] = "error"
            result["errors"].append("Claude configuration path not found")
            return result

        # Create agents directory
        agents_dir = config_path / "agents"

        if not dry_run:
            agents_dir.mkdir(parents=True, exist_ok=True)

        for agent in agents:
            try:
                # Extract agent information
                if hasattr(agent, "metadata") and hasattr(agent.metadata, "name"):
                    name = str(agent.metadata.name)
                    content = str(getattr(agent, "content", ""))
                elif hasattr(agent, "name"):
                    # Direct name attribute
                    name = str(agent.name)
                    content = str(getattr(agent, "content", ""))
                else:
                    # Fallback for dict-like objects
                    name = str(agent.get("name", "unknown"))
                    content = str(agent.get("content", ""))

                if not name or name == "unknown":
                    result["skipped"] += 1
                    result["warnings"].append("Skipped agent with missing name")
                    continue

                # Create agent file path
                agent_file = agents_dir / f"{name}.md"

                if not dry_run:
                    # Write agent content
                    with open(agent_file, "w", encoding="utf-8") as f:
                        f.write(content)

                    # Set appropriate permissions (readable by owner only)
                    agent_file.chmod(0o600)

                result["synced"] += 1

            except Exception as e:
                result["errors"].append(f"Failed to sync agent: {e}")

        if result["errors"]:
            result["status"] = "partial" if result["synced"] > 0 else "error"

        return result

    async def import_agents(self) -> List[Any]:
        """Import agents from Claude Code."""
        agents: List[Any] = []

        config_path = self._get_primary_config_path()
        if not config_path:
            return agents

        agents_dir = config_path / "agents"
        if not agents_dir.exists():
            return agents

        # Find all agent files
        for agent_file in agents_dir.glob("*.md"):
            try:
                with open(agent_file, encoding="utf-8") as f:
                    content = f.read()

                # Create agent-like object
                agent = {
                    "name": agent_file.stem,
                    "content": content,
                    "source": "claude",
                    "file_path": str(agent_file),
                }
                agents.append(agent)

            except Exception as e:
                # Log error but continue
                print(f"Failed to import agent from {agent_file}: {e}")

        return agents

    async def validate_configuration(self) -> List[str]:
        """Validate Claude configuration."""
        errors = []

        # Check if configuration path exists
        config_path = self._get_primary_config_path()
        if not config_path:
            errors.append("Claude configuration directory not found")
            return errors

        # Check settings file
        settings_file = config_path / "settings.json"
        if settings_file.exists():
            try:
                with open(settings_file, encoding="utf-8") as f:
                    json.load(f)
            except json.JSONDecodeError as e:
                errors.append(f"Invalid JSON in settings file: {e}")
            except Exception as e:
                errors.append(f"Cannot read settings file: {e}")

        # Check agents directory
        agents_dir = config_path / "agents"
        if agents_dir.exists():
            if not agents_dir.is_dir():
                errors.append("Agents path exists but is not a directory")
            else:
                # Check agent files
                agent_files = list(agents_dir.glob("*.md"))
                if not agent_files:
                    errors.append("No agent files found in agents directory")

        return errors

    async def cleanup(self) -> bool:
        """Clean up adapter resources."""
        self._initialized = False
        self._installation_path = None
        self._version = None
        return True

    async def backup(self) -> Optional[Path]:
        """Create backup of Claude configuration."""
        config_path = self._get_primary_config_path()
        if not config_path:
            return None

        try:
            import shutil
            from datetime import datetime, timezone

            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            backup_name = f"claude_backup_{timestamp}"
            backup_dir = config_path.parent / "backups" / backup_name

            # Create backup directory
            backup_dir.mkdir(parents=True, exist_ok=True)

            # Copy configuration files
            if config_path.exists():
                shutil.copytree(config_path, backup_dir / "config", dirs_exist_ok=True)

            return backup_dir

        except Exception as e:
            print(f"Failed to create backup: {e}")
            return None

    async def restore(self, backup_path: Path) -> bool:
        """Restore Claude configuration from backup."""
        config_path = self._get_primary_config_path()
        if not config_path or not backup_path.exists():
            return False

        try:
            import shutil

            backup_config = backup_path / "config"
            if backup_config.exists():
                # Remove existing config
                if config_path.exists():
                    shutil.rmtree(config_path)

                # Restore from backup
                shutil.copytree(backup_config, config_path)
                return True

        except Exception as e:
            print(f"Failed to restore backup: {e}")

        return False

    async def get_version_info(self) -> Optional[str]:
        """Get Claude version information."""
        try:
            # Try command line first
            result = subprocess.run(
                ["claude", "--version"], capture_output=True, text=True, timeout=5, check=False  # noqa: S607,S603
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        # Try to read from application info
        if self._installation_path:
            if platform.system() == "Darwin" and self._installation_path.name.endswith(".app"):
                # macOS app bundle
                plist_path = self._installation_path / "Contents" / "Info.plist"
                if plist_path.exists():
                    try:
                        import plistlib

                        with open(plist_path, "rb") as f:
                            plist = plistlib.load(f)
                        return plist.get("CFBundleShortVersionString")
                    except Exception:  # noqa: S110
                        pass

        return None

    async def migrate_from(self, source_adapter: "AbstractAdapter") -> Dict[str, Any]:
        """Migrate from another adapter to Claude."""
        result = {
            "migrated": 0,
            "errors": [],
            "warnings": [],
        }

        try:
            # Import agents from source
            source_agents = await source_adapter.import_agents()

            if source_agents:
                # Sync agents to Claude
                sync_result = await self.sync_agents(source_agents)
                result["migrated"] = sync_result.get("synced", 0)
                result["errors"].extend(sync_result.get("errors", []))
                result["warnings"].extend(sync_result.get("warnings", []))

            # Try to migrate configuration if possible
            try:
                source_config = await source_adapter.get_configuration()
                if source_config:
                    # Filter and adapt configuration for Claude
                    claude_config = self._adapt_configuration(source_config, source_adapter.name)
                    if claude_config:
                        await self.set_configuration(claude_config)
                        result["warnings"].append("Configuration migrated (some settings may need manual adjustment)")
            except Exception as e:
                result["warnings"].append(f"Could not migrate configuration: {e}")

        except Exception as e:
            result["errors"].append(f"Migration failed: {e}")

        return result

    def _adapt_configuration(self, source_config: Dict[str, Any], source_type: str) -> Dict[str, Any]:
        """Adapt configuration from another tool to Claude format."""
        adapted = {}

        # Common configuration mappings
        if "theme" in source_config:
            adapted["theme"] = source_config["theme"]

        if "font_size" in source_config:
            adapted["fontSize"] = source_config["font_size"]

        if "auto_save" in source_config:
            adapted["autoSave"] = source_config["auto_save"]

        # Tool-specific adaptations
        if source_type == "cursor":
            # Cursor-specific adaptations
            if "rules" in source_config:
                adapted["custom_instructions"] = source_config["rules"]

        return adapted


# Register the adapter
def register_claude_adapter():
    """Register the Claude adapter with the factory."""
    from myai.integrations.factory import get_adapter_factory

    factory = get_adapter_factory()
    factory.register_adapter_class("claude", ClaudeAdapter)
