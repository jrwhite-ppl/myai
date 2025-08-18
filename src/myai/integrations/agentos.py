"""
Agent-OS integration adapter.

This module provides hidden integration with Agent-OS, allowing MyAI to sync with
Agent-OS while presenting a unified MyAI interface to users. The integration is
designed to be transparent and maintain compatibility with existing Agent-OS workflows.
"""

import json
import shutil
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


class AgentOSManager(AbstractAdapter):
    """Hidden integration manager for Agent-OS compatibility."""

    def __init__(self, name: str = "agentos", config: Optional[Dict[str, Any]] = None):
        super().__init__(name, config)
        self._agentos_path: Optional[Path] = None
        self._myai_path: Optional[Path] = None
        self._version: Optional[str] = None
        self._path_mappings: Dict[str, str] = {}

    @property
    def info(self) -> AdapterInfo:
        """Get adapter information."""
        if not self._info:
            self._info = AdapterInfo(
                name=self.name,
                display_name="Agent-OS (Hidden)",
                description="Hidden integration layer for Agent-OS compatibility",
                version="1.0.0",
                tool_name="Agent-OS",
                tool_version=self._version,
                capabilities={
                    AdapterCapability.READ_CONFIG,
                    AdapterCapability.SYNC_AGENTS,
                    AdapterCapability.MIGRATION,
                    AdapterCapability.BACKUP_RESTORE,
                    AdapterCapability.VALIDATION,
                },
                status=AdapterStatus.UNKNOWN,
                config_path=self._agentos_path,
                installation_path=self._agentos_path,
            )
        return self._info

    def _detect_agentos_installation(self) -> bool:
        """Detect if Agent-OS is installed and configured."""
        # Check for .agent-os directory in user home
        home = Path.home()
        agentos_dir = home / ".agent-os"

        if agentos_dir.exists() and agentos_dir.is_dir():
            self._agentos_path = agentos_dir
            return True

        # Check for agentos command in PATH
        try:
            result = subprocess.run(
                ["agentos", "--version"], capture_output=True, text=True, timeout=5, check=False  # noqa: S603,S607
            )
            if result.returncode == 0:
                return True
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return False

    def _setup_path_mappings(self) -> None:
        """Create path mappings between Agent-OS and MyAI directories."""
        if not self._agentos_path:
            return

        home = Path.home()
        myai_path = home / ".myai"

        # Create MyAI directory if it doesn't exist
        myai_path.mkdir(exist_ok=True)

        self._myai_path = myai_path

        # Map Agent-OS paths to MyAI paths
        self._path_mappings = {
            str(self._agentos_path / "agents"): str(myai_path / "agents"),
            str(self._agentos_path / "config"): str(myai_path / "config"),
            str(self._agentos_path / "templates"): str(myai_path / "templates"),
            str(self._agentos_path / "hooks"): str(myai_path / "data" / "hooks"),
        }

    async def initialize(self) -> bool:
        """Initialize the Agent-OS adapter."""
        try:
            if not self._detect_agentos_installation():
                if not self._info:
                    self._info = self.info
                self._info.status = AdapterStatus.AVAILABLE
                return True  # Not an error if Agent-OS isn't installed

            # Try to get version information
            self._version = await self.get_version_info()

            # Setup path mappings
            self._setup_path_mappings()

            if not self._info:
                self._info = self.info
            self._info.status = AdapterStatus.CONFIGURED

            self._initialized = True
            return True

        except Exception as e:
            if not self._info:
                self._info = self.info
            self._info.status = AdapterStatus.ERROR
            self._info.error_message = str(e)
            return False

    async def detect_installation(self) -> bool:
        """Detect if Agent-OS is installed."""
        return self._detect_agentos_installation()

    async def get_status(self) -> AdapterStatus:
        """Get current adapter status."""
        if not self._initialized:
            return AdapterStatus.UNKNOWN

        if not self._detect_agentos_installation():
            return AdapterStatus.AVAILABLE

        return AdapterStatus.CONFIGURED

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
            # Check Agent-OS installation
            is_installed = await self.detect_installation()
            health["checks"]["installation"] = {
                "status": "pass" if is_installed else "warning",
                "message": f"Agent-OS {'found' if is_installed else 'not found'}",
            }

            if not is_installed:
                health["warnings"].append("Agent-OS not detected - hidden integration disabled")
                return health

            # Check Agent-OS directory structure
            if self._agentos_path:
                required_dirs = ["agents", "config"]
                for dir_name in required_dirs:
                    dir_path = self._agentos_path / dir_name
                    health["checks"][f"{dir_name}_directory"] = {
                        "status": "pass" if dir_path.exists() else "warning",
                        "message": f"{dir_name.title()} directory {'exists' if dir_path.exists() else 'missing'}",
                        "path": str(dir_path),
                    }

            # Check MyAI directory
            if self._myai_path:
                health["checks"]["myai_directory"] = {
                    "status": "pass",
                    "message": f"MyAI directory: {self._myai_path}",
                    "path": str(self._myai_path),
                }

            # Check version
            version = await self.get_version_info()
            health["checks"]["version"] = {
                "status": "pass" if version else "warning",
                "message": f"Version: {version or 'unknown'}",
            }

        except Exception as e:
            health["status"] = "unhealthy"
            health["errors"].append(f"Health check failed: {e}")

        from datetime import datetime, timezone

        health["timestamp"] = datetime.now(timezone.utc).isoformat()

        return health

    async def get_configuration(self) -> Dict[str, Any]:
        """Get Agent-OS configuration."""
        if not self._agentos_path:
            return {}

        config = {}
        config_file = self._agentos_path / "config" / "config.json"

        if config_file.exists():
            try:
                with open(config_file, encoding="utf-8") as f:
                    config = json.load(f)
            except json.JSONDecodeError as e:
                msg = f"Invalid JSON in Agent-OS config: {e}"
                raise AdapterConfigError(msg, self.name) from e

        return config

    async def set_configuration(self, config: Dict[str, Any]) -> bool:
        """Set Agent-OS configuration."""
        if not self._agentos_path:
            return False

        config_dir = self._agentos_path / "config"
        config_dir.mkdir(exist_ok=True)

        config_file = config_dir / "config.json"

        try:
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            msg = f"Failed to write Agent-OS config: {e}"
            raise AdapterConfigError(msg, self.name) from e

    async def sync_agents(self, agents: List[Any], *, dry_run: bool = False) -> Dict[str, Any]:
        """Sync agents to Agent-OS (hidden operation)."""
        result = {
            "status": "success",
            "synced": 0,
            "skipped": 0,
            "errors": [],
            "warnings": [],
            "dry_run": dry_run,
        }

        if not self._agentos_path:
            result["status"] = "skipped"
            result["warnings"].append("Agent-OS not detected - sync skipped")
            return result

        agents_dir = self._agentos_path / "agents"

        if not dry_run:
            agents_dir.mkdir(exist_ok=True)

        for agent in agents:
            try:
                # Extract agent information
                if hasattr(agent, "metadata") and hasattr(agent.metadata, "name"):
                    name = str(agent.metadata.name)
                    content = str(getattr(agent, "content", ""))
                elif hasattr(agent, "name"):
                    name = str(agent.name)
                    content = str(getattr(agent, "content", ""))
                else:
                    name = str(agent.get("name", "unknown"))
                    content = str(agent.get("content", ""))

                if not name or name == "unknown":
                    result["skipped"] += 1
                    result["warnings"].append("Skipped agent with missing name")
                    continue

                # Transform content for Agent-OS compatibility
                transformed_content = self._transform_content_for_agentos(content)

                # Create agent file path
                agent_file = agents_dir / f"{name}.md"

                if not dry_run:
                    # Write agent content
                    with open(agent_file, "w", encoding="utf-8") as f:
                        f.write(transformed_content)

                    # Set appropriate permissions
                    agent_file.chmod(0o644)

                result["synced"] += 1

            except Exception as e:
                result["errors"].append(f"Failed to sync agent '{name}': {e}")

        if result["errors"]:
            result["status"] = "partial" if result["synced"] > 0 else "error"

        return result

    def _transform_content_for_agentos(self, content: str) -> str:
        """Transform MyAI agent content to Agent-OS compatible format."""
        # Remove MyAI-specific references and replace with Agent-OS equivalents
        # Order matters: do more specific replacements first
        transformed = content.replace(".myai", ".agent-os")
        transformed = transformed.replace("MyAI", "Agent-OS")
        transformed = transformed.replace("myai", "agentos")

        # Add Agent-OS compatibility header if not present
        if not transformed.startswith("# Agent-OS Compatible"):
            header = "# Agent-OS Compatible Agent\n\n"
            transformed = header + transformed

        return transformed

    async def import_agents(self) -> List[Any]:
        """Import agents from Agent-OS."""
        agents: List[Any] = []

        if not self._agentos_path:
            return agents

        agents_dir = self._agentos_path / "agents"
        if not agents_dir.exists():
            return agents

        # Find all agent files
        for agent_file in agents_dir.glob("*.md"):
            try:
                with open(agent_file, encoding="utf-8") as f:
                    content = f.read()

                # Transform content from Agent-OS to MyAI format
                transformed_content = self._transform_content_from_agentos(content)

                # Create agent-like object
                agent = {
                    "name": agent_file.stem,
                    "content": transformed_content,
                    "source": "agentos",
                    "file_path": str(agent_file),
                }
                agents.append(agent)

            except Exception as e:
                print(f"Failed to import agent from {agent_file}: {e}")

        return agents

    def _transform_content_from_agentos(self, content: str) -> str:
        """Transform Agent-OS content to MyAI format."""
        # Replace Agent-OS references with MyAI equivalents
        transformed = content.replace("Agent-OS", "MyAI")
        transformed = transformed.replace("agentos", "myai")
        transformed = transformed.replace(".agent-os", ".myai")

        # Remove Agent-OS compatibility headers
        lines = transformed.split("\n")
        if lines and "Agent-OS Compatible" in lines[0]:
            lines = lines[2:]  # Remove header and blank line
            transformed = "\n".join(lines)

        return transformed

    async def validate_configuration(self) -> List[str]:
        """Validate Agent-OS configuration."""
        errors = []

        if not self._agentos_path:
            return errors

        # Check Agent-OS directory structure
        required_dirs = ["agents", "config"]
        for dir_name in required_dirs:
            dir_path = self._agentos_path / dir_name
            if not dir_path.exists():
                errors.append(f"Agent-OS {dir_name} directory missing: {dir_path}")

        # Check configuration file
        config_file = self._agentos_path / "config" / "config.json"
        if config_file.exists():
            try:
                with open(config_file, encoding="utf-8") as f:
                    json.load(f)
            except json.JSONDecodeError as e:
                errors.append(f"Invalid JSON in Agent-OS config: {e}")

        return errors

    async def cleanup(self) -> bool:
        """Clean up adapter resources."""
        self._initialized = False
        self._agentos_path = None
        self._myai_path = None
        self._version = None
        self._path_mappings.clear()
        return True

    async def backup(self) -> Optional[Path]:
        """Create backup of Agent-OS configuration."""
        if not self._agentos_path:
            return None

        try:
            from datetime import datetime, timezone

            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            backup_name = f"agentos_backup_{timestamp}"
            backup_dir = Path.home() / ".myai" / "backups" / backup_name

            # Create backup directory
            backup_dir.mkdir(parents=True, exist_ok=True)

            # Backup Agent-OS directory
            if self._agentos_path.exists():
                shutil.copytree(self._agentos_path, backup_dir / "agentos", dirs_exist_ok=True)

            return backup_dir

        except Exception as e:
            print(f"Failed to create Agent-OS backup: {e}")
            return None

    async def restore(self, backup_path: Path) -> bool:
        """Restore Agent-OS configuration from backup."""
        if not self._agentos_path or not backup_path.exists():
            return False

        try:
            backup_agentos = backup_path / "agentos"
            if backup_agentos.exists():
                # Remove existing Agent-OS directory
                if self._agentos_path.exists():
                    shutil.rmtree(self._agentos_path)

                # Restore from backup
                shutil.copytree(backup_agentos, self._agentos_path)
                return True

        except Exception as e:
            print(f"Failed to restore Agent-OS backup: {e}")

        return False

    async def get_version_info(self) -> Optional[str]:
        """Get Agent-OS version information."""
        try:
            # Try command line first
            result = subprocess.run(
                ["agentos", "--version"], capture_output=True, text=True, timeout=5, check=False  # noqa: S603,S607
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        # Try to read from package info if available
        try:
            import pkg_resources

            return pkg_resources.get_distribution("agent-os").version
        except Exception:
            # Silent fallback for optional dependency
            return None

        return None

    async def migrate_from(self, source_adapter: "AbstractAdapter") -> Dict[str, Any]:
        """Migrate from another adapter to Agent-OS."""
        result = {
            "migrated": 0,
            "errors": [],
            "warnings": [],
        }

        try:
            # Import agents from source
            source_agents = await source_adapter.import_agents()

            if source_agents:
                # Sync agents to Agent-OS
                sync_result = await self.sync_agents(source_agents)
                result["migrated"] = sync_result.get("synced", 0)
                result["errors"].extend(sync_result.get("errors", []))
                result["warnings"].extend(sync_result.get("warnings", []))

        except Exception as e:
            result["errors"].append(f"Migration failed: {e}")

        return result


# Register the adapter
def register_agentos_adapter():
    """Register the Agent-OS adapter with the factory."""
    from myai.integrations.factory import get_adapter_factory

    factory = get_adapter_factory()
    factory.register_adapter_class("agentos", AgentOSManager)
