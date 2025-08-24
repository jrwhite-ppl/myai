"""Tests for JSON content manager utilities."""

import json
import tempfile
from pathlib import Path

from myai.utils.json_content_manager import JsonContentManager, update_claude_settings


class TestJsonContentManager:
    """Test JsonContentManager class."""

    def test_update_sections_preserves_unknown_keys(self):
        """Test that unknown keys are preserved when updating sections."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.json"

            # Create initial file with both managed and unmanaged sections
            initial_data = {
                "managed_section": {"old": "value"},
                "user_section": {"custom": "data"},
                "another_user_section": {"more": "stuff"},
            }
            with open(file_path, "w") as f:
                json.dump(initial_data, f)

            # Update only managed section
            manager = JsonContentManager(["managed_section"])
            updates = {"managed_section": {"new": "value"}}
            manager.update_sections(file_path, updates, preserve_unknown=True)

            # Verify result
            with open(file_path) as f:
                result = json.load(f)

            assert result["managed_section"] == {"new": "value"}
            assert result["user_section"] == {"custom": "data"}
            assert result["another_user_section"] == {"more": "stuff"}

    def test_update_sections_without_preserve_unknown(self):
        """Test that unknown keys are removed when preserve_unknown=False."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.json"

            # Create initial file
            initial_data = {"managed_section": {"old": "value"}, "user_section": {"custom": "data"}}
            with open(file_path, "w") as f:
                json.dump(initial_data, f)

            # Update with preserve_unknown=False
            manager = JsonContentManager(["managed_section"])
            updates = {"managed_section": {"new": "value"}}
            manager.update_sections(file_path, updates, preserve_unknown=False)

            # Verify result
            with open(file_path) as f:
                result = json.load(f)

            assert result == {"managed_section": {"new": "value"}}
            assert "user_section" not in result


class TestUpdateClaudeSettings:
    """Test update_claude_settings function."""

    def test_update_claude_settings_unwraps_projects_key(self):
        """Test that project config wrapped in 'projects' key is unwrapped correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "settings.local.json"

            # This is how the install command passes the config
            project_config = {
                "projects": {
                    "/Users/test/project": {
                        "model": "claude-3-sonnet-20241022",
                        "permissions": {"allow": ["Bash(uv run:*)", "Bash(npm run:*)"], "deny": ["Read(./.env)"]},
                        "agentsPath": "/Users/test/project/.claude/agents",
                    }
                }
            }

            update_claude_settings(settings_path, project_config)

            # Read and verify the result
            with open(settings_path) as f:
                result = json.load(f)

            # Should NOT have a 'projects' key at root level
            assert "projects" not in result

            # Should have only permissions at root level (not model or agentsPath)
            assert "model" not in result
            assert "agentsPath" not in result
            assert result["permissions"]["allow"] == ["Bash(uv run:*)", "Bash(npm run:*)"]
            assert result["permissions"]["deny"] == ["Read(./.env)"]

    def test_update_claude_settings_preserves_user_permissions(self):
        """Test that user's custom permissions are preserved when updating."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "settings.local.json"

            # Create existing file with user's custom permissions
            existing_content = {
                "permissions": {
                    "allow": [
                        "WebFetch(domain:docs.anthropic.com)",
                        "WebFetch(domain:github.com)",
                        "Bash(uv run:*)",
                        "Bash(make pre-ci:*)",
                        "Bash(custom-command:*)",
                    ],
                    "deny": ["Read(./.env)", "Read(./secrets/**)", "Write(./production/**)"],
                },
                "customUserKey": "should be preserved",
            }

            with open(settings_path, "w") as f:
                json.dump(existing_content, f, indent=2)

            # Update with MyAI config
            project_config = {
                "projects": {
                    "/Users/test/project": {
                        "model": "claude-3-sonnet-20241022",
                        "permissions": {"allow": ["Bash(uv run:*)", "Bash(npm run:*)"], "deny": ["Read(./.env)"]},
                        "agentsPath": "/Users/test/project/.claude/agents",
                    }
                }
            }

            update_claude_settings(settings_path, project_config)

            # Read and verify the result
            with open(settings_path) as f:
                result = json.load(f)

            # Should NOT have a 'projects' key
            assert "projects" not in result

            # Should NOT have model or agentsPath (not managed by MyAI)
            assert "model" not in result
            assert "agentsPath" not in result

            # Should have MyAI's permissions (MyAI manages the permissions section)
            assert result["permissions"]["allow"] == ["Bash(uv run:*)", "Bash(npm run:*)"]
            assert result["permissions"]["deny"] == ["Read(./.env)"]

            # Should preserve non-managed user keys
            assert result["customUserKey"] == "should be preserved"

    def test_update_claude_settings_handles_direct_config(self):
        """Test that config without 'projects' wrapper is handled correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "settings.local.json"

            # Direct config without projects wrapper
            project_config = {
                "model": "claude-3-sonnet-20241022",
                "permissions": {"allow": ["Bash(uv run:*)"], "deny": ["Read(./.env)"]},
                "agentsPath": "/Users/test/.claude/agents",
            }

            update_claude_settings(settings_path, project_config)

            # Read and verify the result
            with open(settings_path) as f:
                result = json.load(f)

            # Should only have permissions (the only managed section)
            assert result == {"permissions": {"allow": ["Bash(uv run:*)"], "deny": ["Read(./.env)"]}}

    def test_update_claude_settings_creates_file_if_missing(self):
        """Test that settings file is created if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "settings.local.json"

            # Ensure file doesn't exist
            assert not settings_path.exists()

            project_config = {
                "projects": {
                    "/Users/test/project": {
                        "permissions": {"allow": ["Bash(uv run:*)", "Bash(make:*)"], "deny": ["Read(./.env)"]}
                    }
                }
            }

            update_claude_settings(settings_path, project_config, create_if_missing=True)

            # File should now exist
            assert settings_path.exists()

            # Verify content
            with open(settings_path) as f:
                result = json.load(f)

            # Should only have permissions, not model or agentsPath
            assert "model" not in result
            assert "agentsPath" not in result
            assert result["permissions"]["allow"] == ["Bash(uv run:*)", "Bash(make:*)"]
            assert result["permissions"]["deny"] == ["Read(./.env)"]

    def test_update_claude_settings_preserves_user_model_and_agentspath(self):
        """Test that user's model and agentsPath settings are preserved."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "settings.local.json"

            # Create existing file with user's model and agentsPath preferences
            existing_content = {
                "model": "claude-3-opus-20240229",  # User's preferred model
                "agentsPath": "/custom/path/to/agents",  # User's custom path
                "permissions": {"allow": ["WebFetch(domain:example.com)"], "deny": ["Write(./production/**)"]},
            }

            with open(settings_path, "w") as f:
                json.dump(existing_content, f, indent=2)

            # Update with MyAI config (only permissions)
            project_config = {
                "projects": {
                    "/Users/test/project": {
                        "permissions": {"allow": ["Bash(uv run:*)", "Bash(npm run:*)"], "deny": ["Read(./.env)"]}
                    }
                }
            }

            update_claude_settings(settings_path, project_config)

            # Read and verify the result
            with open(settings_path) as f:
                result = json.load(f)

            # User's model and agentsPath should be preserved
            assert result["model"] == "claude-3-opus-20240229"
            assert result["agentsPath"] == "/custom/path/to/agents"

            # Permissions should be updated to MyAI's
            assert result["permissions"]["allow"] == ["Bash(uv run:*)", "Bash(npm run:*)"]
            assert result["permissions"]["deny"] == ["Read(./.env)"]
