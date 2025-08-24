"""
Cursor integration adapter.

This module provides integration with Cursor AI code editor,
allowing MyAI to sync agents as .cursorrules files and manage Cursor configurations.
"""

import json
import os
import platform
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from myai.agent.wrapper import get_wrapper_generator
from myai.integrations.base import (
    AbstractAdapter,
    AdapterCapability,
    AdapterConfigError,
    AdapterInfo,
    AdapterStatus,
)


class CursorAdapter(AbstractAdapter):
    """Adapter for Cursor AI code editor integration."""

    def __init__(self, name: str = "cursor", config: Optional[Dict[str, Any]] = None):
        super().__init__(name, config)
        self._config_paths = self._detect_config_paths()
        self._installation_path: Optional[Path] = None
        self._version: Optional[str] = None
        self._rules_directory: Optional[Path] = None
        self.wrapper_generator = get_wrapper_generator()

    @property
    def info(self) -> AdapterInfo:
        """Get adapter information."""
        if not self._info:
            self._info = AdapterInfo(
                name=self.name,
                display_name="Cursor AI",
                description="Integration with Cursor AI code editor",
                version="1.0.0",
                tool_name="Cursor",
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
        """Detect possible Cursor configuration paths."""
        system = platform.system()
        paths = []

        if system == "Darwin":  # macOS
            home = Path.home()
            paths.extend(
                [
                    home / "Library" / "Application Support" / "Cursor",
                    home / ".config" / "cursor",
                    home / ".cursor",
                ]
            )
        elif system == "Windows":
            appdata = os.getenv("APPDATA")
            if appdata:
                paths.extend(
                    [
                        Path(appdata) / "Cursor",
                        Path(appdata) / "cursor",
                    ]
                )

            home = Path.home()
            paths.extend(
                [
                    home / ".config" / "cursor",
                    home / ".cursor",
                ]
            )
        else:  # Linux and others
            home = Path.home()
            paths.extend(
                [
                    home / ".config" / "cursor",
                    home / ".local" / "share" / "cursor",
                    home / ".cursor",
                    Path("/etc/cursor"),
                ]
            )

        return [path for path in paths if path.exists()]

    def _get_primary_config_path(self) -> Optional[Path]:
        """Get the primary configuration path."""
        if self._config_paths:
            return self._config_paths[0]
        return None

    def _detect_installation_paths(self) -> List[Path]:
        """Detect possible Cursor installation paths."""
        system = platform.system()
        paths = []

        if system == "Darwin":  # macOS
            paths.extend(
                [
                    Path("/Applications/Cursor.app"),
                    Path("/usr/local/bin/cursor"),
                    Path("/opt/homebrew/bin/cursor"),
                ]
            )
        elif system == "Windows":
            program_files = os.getenv("PROGRAMFILES")
            program_files_x86 = os.getenv("PROGRAMFILES(X86)")
            localappdata = os.getenv("LOCALAPPDATA")

            if program_files:
                paths.extend(
                    [
                        Path(program_files) / "Cursor",
                    ]
                )

            if program_files_x86:
                paths.extend(
                    [
                        Path(program_files_x86) / "Cursor",
                    ]
                )

            if localappdata:
                paths.extend(
                    [
                        Path(localappdata) / "Programs" / "Cursor",
                    ]
                )
        else:  # Linux and others
            paths.extend(
                [
                    Path("/usr/bin/cursor"),
                    Path("/usr/local/bin/cursor"),
                    Path("/opt/cursor/bin/cursor"),
                    Path.home() / ".local" / "bin" / "cursor",
                    Path("/snap/cursor/current/bin/cursor"),
                ]
            )

        return [path for path in paths if path.exists()]

    def _get_rules_directory(self) -> Path:
        """Get the directory for storing .cursorrules files.

        For project-level integration, this should be the current project's .cursor directory.
        """
        if self._rules_directory:
            return self._rules_directory

        # Project-level rules directory
        cwd = Path.cwd()
        rules_dir = cwd / ".cursor"

        # Only create if we're in a project context
        if cwd != Path.home():
            rules_dir.mkdir(parents=True, exist_ok=True)

        self._rules_directory = rules_dir
        return rules_dir

    async def initialize(self) -> bool:
        """Initialize the Cursor adapter."""
        try:
            # Detect installation
            if not await self.detect_installation():
                if not self._info:
                    self._info = self.info
                self._info.status = AdapterStatus.ERROR
                self._info.error_message = "Cursor not found"
                return False

            # Try to get version information
            self._version = await self.get_version_info()

            # Check configuration
            config_path = self._get_primary_config_path()
            if not self._info:
                self._info = self.info
            if config_path:
                self._info.status = AdapterStatus.CONFIGURED
            else:
                self._info.status = AdapterStatus.AVAILABLE

            # Setup rules directory
            self._get_rules_directory()

            self._initialized = True
            return True

        except Exception as e:
            if not self._info:
                self._info = self.info
            self._info.status = AdapterStatus.ERROR
            self._info.error_message = str(e)
            return False

    async def detect_installation(self) -> bool:
        """Detect if Cursor is installed."""
        # Check for executable
        installation_paths = self._detect_installation_paths()

        for path in installation_paths:
            if path.exists():
                self._installation_path = path
                return True

        # Try to run cursor command
        try:
            result = subprocess.run(
                ["cursor", "--version"], capture_output=True, text=True, timeout=5, check=False  # noqa: S607,S603
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
                "message": f"Cursor {'found' if is_installed else 'not found'}",
            }

            if not is_installed:
                health["status"] = "unhealthy"
                health["errors"].append("Cursor installation not detected")
                return health

            # Check configuration
            config_path = self._get_primary_config_path()
            health["checks"]["configuration"] = {
                "status": "pass" if config_path else "warning",
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

            # Check rules directory
            rules_dir = self._get_rules_directory()
            cwd = Path.cwd()

            if cwd == Path.home():
                health["checks"]["rules_directory"] = {
                    "status": "warning",
                    "message": "Cursor integration requires project context",
                    "path": None,
                    "rules_count": 0,
                }
                health["warnings"].append("Run from within a project directory to use Cursor integration")
            else:
                health["checks"]["rules_directory"] = {
                    "status": "pass" if rules_dir.exists() else "info",
                    "message": f"Project rules directory: {rules_dir}",
                    "path": str(rules_dir),
                    "rules_count": len(list(rules_dir.glob("*.cursorrules"))) if rules_dir.exists() else 0,
                }

            # Check version
            version = await self.get_version_info()
            health["checks"]["version"] = {
                "status": "pass" if version else "warning",
                "message": f"Version: {version or 'unknown'}",
            }

            if not version:
                health["warnings"].append("Could not determine Cursor version")

        except Exception as e:
            health["status"] = "unhealthy"
            health["errors"].append(f"Health check failed: {e}")

        from datetime import datetime, timezone

        health["timestamp"] = datetime.now(timezone.utc).isoformat()

        return health

    async def get_configuration(self) -> Dict[str, Any]:
        """Get Cursor configuration."""
        config = {}

        # Get main settings
        config_path = self._get_primary_config_path()
        if config_path:
            settings_file = config_path / "settings.json"
            if settings_file.exists():
                try:
                    with open(settings_file, encoding="utf-8") as f:
                        config["settings"] = json.load(f)
                except json.JSONDecodeError as e:
                    msg = f"Invalid JSON in settings file: {e}"
                    raise AdapterConfigError(msg, self.name) from e

        # Get rules files
        rules_dir = self._get_rules_directory()
        if rules_dir.exists():
            config["rules"] = {}
            for rules_file in rules_dir.glob("*.cursorrules"):
                try:
                    with open(rules_file, encoding="utf-8") as f:
                        config["rules"][rules_file.stem] = f.read()
                except Exception as e:
                    config["rules"][rules_file.stem] = f"Error reading file: {e}"

        return config

    async def set_configuration(self, config: Dict[str, Any]) -> bool:
        """Set Cursor configuration."""
        success = True

        # Handle settings
        if "settings" in config:
            config_path = self._get_primary_config_path()
            if not config_path:
                # Create default config path
                if platform.system() == "Darwin":
                    config_path = Path.home() / "Library" / "Application Support" / "Cursor"
                else:
                    config_path = Path.home() / ".config" / "cursor"

            config_path.mkdir(parents=True, exist_ok=True)
            settings_file = config_path / "settings.json"

            try:
                # Merge with existing settings if they exist
                existing_settings = {}
                if settings_file.exists():
                    with open(settings_file, encoding="utf-8") as f:
                        existing_settings = json.load(f)

                merged_settings = {**existing_settings, **config["settings"]}

                with open(settings_file, "w", encoding="utf-8") as f:
                    json.dump(merged_settings, f, indent=2, ensure_ascii=False)

            except Exception as e:
                success = False
                msg = f"Failed to write settings: {e}"
                raise AdapterConfigError(msg, self.name) from e

        # Handle rules
        if "rules" in config:
            rules_dir = self._get_rules_directory()

            for rule_name, rule_content in config["rules"].items():
                try:
                    rules_file = rules_dir / f"{rule_name}.cursorrules"
                    with open(rules_file, "w", encoding="utf-8") as f:
                        f.write(rule_content)

                    # Set appropriate permissions
                    rules_file.chmod(0o644)

                except Exception as e:
                    success = False
                    print(f"Failed to write rule {rule_name}: {e}")

        return success

    async def sync_agents(self, agents: List[Any], *, dry_run: bool = False) -> Dict[str, Any]:
        """Sync agents to Cursor as project-level .cursorrules files.

        This creates .cursor/ directory in the current project with agent rules.
        """
        result = {
            "status": "success",
            "synced": 0,
            "skipped": 0,
            "errors": [],
            "warnings": [],
            "dry_run": dry_run,
        }

        # Check if we're in a project context
        cwd = Path.cwd()
        if cwd == Path.home():
            result["status"] = "error"
            result["errors"].append("Cannot sync Cursor rules to home directory. Please run from within a project.")
            return result

        rules_dir = self._get_rules_directory()

        if not dry_run:
            rules_dir.mkdir(parents=True, exist_ok=True)

        for agent in agents:
            try:
                # Extract agent information
                if hasattr(agent, "metadata") and hasattr(agent.metadata, "name"):
                    name = str(agent.metadata.name)
                    content = str(getattr(agent, "content", ""))
                    category = str(getattr(agent.metadata, "category", None))
                elif hasattr(agent, "name"):
                    # Direct name attribute
                    name = str(agent.name)
                    content = str(getattr(agent, "content", ""))
                    category = str(getattr(agent, "category", None)) if hasattr(agent, "category") else None
                else:
                    # Fallback for dict-like objects
                    name = str(agent.get("name", "unknown"))
                    content = str(agent.get("content", ""))
                    category = str(agent.get("category", None))

                if not name or name == "unknown":
                    result["skipped"] += 1
                    result["warnings"].append("Skipped agent with missing name")
                    continue

                # Create rule file path (using .mdc for MDC format)
                rules_file = rules_dir / "rules" / f"{name}.mdc"

                if not dry_run:
                    # Ensure rules subdirectory exists
                    rules_file.parent.mkdir(parents=True, exist_ok=True)

                    # Generate Cursor MDC content with minimal wrapper
                    if hasattr(agent, "metadata"):
                        # Agent is an AgentSpecification, use wrapper generator
                        cursor_content = self.wrapper_generator.generate_minimal_cursor_wrapper(agent)
                    else:
                        # Fallback for dict-like objects
                        cursor_content = self._generate_project_cursor_rules(name, content, category)

                    # Write rule file
                    with open(rules_file, "w", encoding="utf-8") as f:
                        f.write(cursor_content)

                    # Set appropriate permissions
                    rules_file.chmod(0o644)

                result["synced"] += 1

            except Exception as e:
                result["errors"].append(f"Failed to sync agent '{name}': {e}")

        # Add project-level integration message
        if not dry_run and result["synced"] > 0:
            result["message"] = f"Synced {result['synced']} agents to project .cursor/ directory"

        if result["errors"]:
            result["status"] = "partial" if result["synced"] > 0 else "error"

        return result

    def _generate_project_cursor_rules(self, name: str, content: str, category: Optional[str] = None) -> str:
        _ = name  # Unused in project-level rules
        _ = category  # Unused in project-level rules
        """Generate .cursorrules content for project-level integration."""
        # For project-level rules, we use the raw agent content directly
        # as Cursor will apply these rules to the project context
        return content.strip()

    async def import_agents(self) -> List[Any]:
        """Import agents from Cursor rules files."""
        agents: List[Any] = []

        rules_dir = self._get_rules_directory()
        if not rules_dir.exists():
            return agents

        # Find all rule files (.mdc files in rules subdirectory)
        rules_subdir = rules_dir / "rules"
        if rules_subdir.exists():
            for rules_file in rules_subdir.glob("*.mdc"):
                try:
                    with open(rules_file, encoding="utf-8") as f:
                        content = f.read()

                    # Create agent-like object
                    agent = {
                        "name": rules_file.stem,
                        "content": content,
                        "source": "cursor",
                        "file_path": str(rules_file),
                        "category": self._extract_category_from_rules(content),
                    }
                    agents.append(agent)

                except Exception as e:
                    # Log error but continue
                    print(f"Failed to import agent from {rules_file}: {e}")

        return agents

    def _extract_category_from_rules(self, content: str) -> Optional[str]:
        """Extract category from rules content."""
        lines = content.split("\n")
        for line in lines:
            if line.strip().startswith("# Category:"):
                return line.split(":", 1)[1].strip()
        return None

    async def validate_configuration(self) -> List[str]:
        """Validate Cursor configuration."""
        errors = []

        # Check rules directory
        rules_dir = self._get_rules_directory()
        if not rules_dir.exists():
            errors.append("Cursor rules directory does not exist")
        elif not rules_dir.is_dir():
            errors.append("Rules path exists but is not a directory")

        # Check settings file if it exists
        config_path = self._get_primary_config_path()
        if config_path:
            settings_file = config_path / "settings.json"
            if settings_file.exists():
                try:
                    with open(settings_file, encoding="utf-8") as f:
                        json.load(f)
                except json.JSONDecodeError as e:
                    errors.append(f"Invalid JSON in settings file: {e}")
                except Exception as e:
                    errors.append(f"Cannot read settings file: {e}")

        # Check rule files
        if rules_dir.exists():
            rule_files = list(rules_dir.glob("*.cursorrules"))
            for rule_file in rule_files:
                try:
                    # Check if file is readable
                    with open(rule_file, encoding="utf-8") as f:
                        content = f.read()

                    # Basic validation - check if content is not empty
                    if not content.strip():
                        errors.append(f"Rule file {rule_file.name} is empty")

                except Exception as e:
                    errors.append(f"Cannot read rule file {rule_file.name}: {e}")

        return errors

    async def cleanup(self) -> bool:
        """Clean up adapter resources."""
        self._initialized = False
        self._installation_path = None
        self._version = None
        return True

    async def backup(self) -> Optional[Path]:
        """Create backup of Cursor configuration."""
        try:
            import shutil
            from datetime import datetime, timezone

            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            backup_name = f"cursor_backup_{timestamp}"
            backup_dir = Path.home() / ".myai" / "backups" / backup_name

            # Create backup directory
            backup_dir.mkdir(parents=True, exist_ok=True)

            # Backup configuration files
            config_path = self._get_primary_config_path()
            if config_path and config_path.exists():
                shutil.copytree(config_path, backup_dir / "config", dirs_exist_ok=True)

            # Backup rules files
            rules_dir = self._get_rules_directory()
            if rules_dir.exists():
                shutil.copytree(rules_dir, backup_dir / "rules", dirs_exist_ok=True)

            return backup_dir

        except Exception as e:
            print(f"Failed to create backup: {e}")
            return None

    async def restore(self, backup_path: Path) -> bool:
        """Restore Cursor configuration from backup."""
        try:
            import shutil

            # Restore configuration
            backup_config = backup_path / "config"
            if backup_config.exists():
                config_path = self._get_primary_config_path()
                if not config_path:
                    if platform.system() == "Darwin":
                        config_path = Path.home() / "Library" / "Application Support" / "Cursor"
                    else:
                        config_path = Path.home() / ".config" / "cursor"

                if config_path.exists():
                    shutil.rmtree(config_path)

                shutil.copytree(backup_config, config_path)

            # Restore rules
            backup_rules = backup_path / "rules"
            if backup_rules.exists():
                rules_dir = self._get_rules_directory()
                if rules_dir.exists():
                    shutil.rmtree(rules_dir)

                shutil.copytree(backup_rules, rules_dir)

            return True

        except Exception as e:
            print(f"Failed to restore backup: {e}")
            return False

    async def get_version_info(self) -> Optional[str]:
        """Get Cursor version information."""
        try:
            # Try command line first
            result = subprocess.run(
                ["cursor", "--version"], capture_output=True, text=True, timeout=5, check=False  # noqa: S607,S603
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
        """Migrate from another adapter to Cursor."""
        result = {
            "migrated": 0,
            "errors": [],
            "warnings": [],
        }

        try:
            # Import agents from source
            source_agents = await source_adapter.import_agents()

            if source_agents:
                # Sync agents to Cursor as rules
                sync_result = await self.sync_agents(source_agents)
                result["migrated"] = sync_result.get("synced", 0)
                result["errors"].extend(sync_result.get("errors", []))
                result["warnings"].extend(sync_result.get("warnings", []))

            # Try to migrate configuration if possible
            try:
                source_config = await source_adapter.get_configuration()
                if source_config:
                    # Filter and adapt configuration for Cursor
                    cursor_config = self._adapt_configuration(source_config, source_adapter.name)
                    if cursor_config:
                        await self.set_configuration(cursor_config)
                        result["warnings"].append("Configuration migrated (some settings may need manual adjustment)")
            except Exception as e:
                result["warnings"].append(f"Could not migrate configuration: {e}")

        except Exception as e:
            result["errors"].append(f"Migration failed: {e}")

        return result

    def _adapt_configuration(self, source_config: Dict[str, Any], source_type: str) -> Dict[str, Any]:
        """Adapt configuration from another tool to Cursor format."""
        adapted = {}

        # Common configuration mappings
        settings = {}

        if "theme" in source_config:
            settings["workbench.colorTheme"] = source_config["theme"]

        if "font_size" in source_config:
            settings["editor.fontSize"] = source_config["font_size"]

        if "auto_save" in source_config:
            settings["files.autoSave"] = "afterDelay" if source_config["auto_save"] else "off"

        # Tool-specific adaptations
        if source_type == "claude":
            # Claude-specific adaptations
            if "custom_instructions" in source_config:
                # Convert to rules format
                adapted["rules"] = {"claude_instructions": source_config["custom_instructions"]}

        if settings:
            adapted["settings"] = settings

        return adapted


# Register the adapter
def register_cursor_adapter():
    """Register the Cursor adapter with the factory."""
    from myai.integrations.factory import get_adapter_factory

    factory = get_adapter_factory()
    factory.register_adapter_class("cursor", CursorAdapter)
