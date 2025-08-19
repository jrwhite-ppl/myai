"""
Tests for interactive CLI utilities.
"""

from unittest.mock import patch

import pytest
import typer

from myai.cli.interactive import (
    InteractivePrompts,
    validate_email,
    validate_name,
    validate_url,
    validate_version,
)


class TestInteractivePrompts:
    """Test cases for InteractivePrompts class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.prompts = InteractivePrompts()

    @patch("myai.cli.interactive.IntPrompt.ask")
    @patch("myai.cli.interactive.console")
    def test_single_selection_valid_choice(self, mock_console, mock_prompt):
        """Test single selection with valid choice."""
        mock_prompt.return_value = 2
        choices = ["option1", "option2", "option3"]

        result = self.prompts.single_selection("Test Title", choices)

        assert result == "option2"
        mock_console.print.assert_called()

    @patch("myai.cli.interactive.IntPrompt.ask")
    @patch("myai.cli.interactive.console")
    def test_single_selection_with_descriptions(self, mock_console, mock_prompt):
        """Test single selection with descriptions."""
        mock_prompt.return_value = 1
        choices = ["option1", "option2"]
        descriptions = ["desc1", "desc2"]

        result = self.prompts.single_selection("Test Title", choices, descriptions)

        assert result == "option1"
        mock_console.print.assert_called()

    @patch("myai.cli.interactive.IntPrompt.ask")
    @patch("myai.cli.interactive.console")
    def test_single_selection_with_default(self, _mock_console, mock_prompt):
        """Test single selection with default value."""
        mock_prompt.return_value = 2  # Default will be used
        choices = ["option1", "option2", "option3"]

        result = self.prompts.single_selection("Test Title", choices, default=1)

        assert result == "option2"
        mock_prompt.assert_called_with("\nSelect option [default: 2]", default=2)

    def test_single_selection_empty_choices(self):
        """Test single selection with empty choices."""
        with patch("myai.cli.interactive.console") as mock_console:
            with pytest.raises(typer.Exit):
                self.prompts.single_selection("Test Title", [])

            mock_console.print.assert_called_with("[red]No choices available[/red]")

    @patch("myai.cli.interactive.IntPrompt.ask")
    @patch("myai.cli.interactive.console")
    def test_single_selection_invalid_choice(self, mock_console, mock_prompt):
        """Test single selection with invalid choice then valid choice."""
        mock_prompt.side_effect = [5, 2]  # First invalid, then valid
        choices = ["option1", "option2", "option3"]

        result = self.prompts.single_selection("Test Title", choices)

        assert result == "option2"
        # Should print error message for invalid choice
        mock_console.print.assert_any_call("[red]Please enter a number between 1 and 3[/red]")

    @patch("myai.cli.interactive.IntPrompt.ask")
    @patch("myai.cli.interactive.console")
    def test_single_selection_keyboard_interrupt(self, mock_console, mock_prompt):
        """Test single selection with keyboard interrupt."""
        mock_prompt.side_effect = KeyboardInterrupt()
        choices = ["option1", "option2"]

        with pytest.raises(typer.Exit):
            self.prompts.single_selection("Test Title", choices)

        mock_console.print.assert_any_call("\n[yellow]Selection cancelled[/yellow]")

    @patch("myai.cli.interactive.Prompt.ask")
    @patch("myai.cli.interactive.console")
    def test_multi_selection_valid(self, _mock_console, mock_prompt):
        """Test multi-selection with valid input."""
        mock_prompt.return_value = "1,3"
        choices = ["option1", "option2", "option3"]

        result = self.prompts.multi_selection("Test Title", choices)

        assert result == ["option1", "option3"]

    @patch("myai.cli.interactive.Prompt.ask")
    @patch("myai.cli.interactive.console")
    def test_multi_selection_with_invalid_input(self, mock_console, mock_prompt):
        """Test multi-selection with invalid input format."""
        # Input has invalid format mixed with valid - should extract valid parts
        mock_prompt.return_value = "invalid,1,2,3"  # Has invalid part but valid selections
        choices = ["option1", "option2", "option3", "option4"]

        result = self.prompts.multi_selection("Test Title", choices)

        assert result == ["option1", "option2", "option3"]
        # Should show error for invalid format
        mock_console.print.assert_any_call("[red]Invalid number: invalid[/red]")

    @patch("myai.cli.interactive.Prompt.ask")
    @patch("myai.cli.interactive.console")
    def test_multi_selection_all_keyword(self, _mock_console, mock_prompt):
        """Test multi-selection with 'all' keyword."""
        mock_prompt.return_value = "all"
        choices = ["option1", "option2", "option3"]

        result = self.prompts.multi_selection("Test Title", choices)

        assert result == choices

    @patch("myai.cli.interactive.Prompt.ask")
    @patch("myai.cli.interactive.console")
    def test_multi_selection_min_selections(self, mock_console, mock_prompt):
        """Test multi-selection with minimum selections requirement."""
        mock_prompt.side_effect = ["1", "1,2"]  # First too few, then valid
        choices = ["option1", "option2", "option3"]

        result = self.prompts.multi_selection("Test Title", choices, min_selections=2)

        assert result == ["option1", "option2"]
        mock_console.print.assert_any_call("[red]Please select at least 2 option(s)[/red]")

    @patch("myai.cli.interactive.Prompt.ask")
    @patch("myai.cli.interactive.console")
    def test_multi_selection_max_selections(self, mock_console, mock_prompt):
        """Test multi-selection with maximum selections limit."""
        mock_prompt.side_effect = ["1,2,3", "1,2"]  # First too many, then valid
        choices = ["option1", "option2", "option3"]

        result = self.prompts.multi_selection("Test Title", choices, max_selections=2)

        assert result == ["option1", "option2"]
        mock_console.print.assert_any_call("[red]Please select at most 2 option(s)[/red]")

    @patch("myai.cli.interactive.Prompt.ask")
    @patch("myai.cli.interactive.console")
    def test_text_input_valid(self, _mock_console, mock_prompt):
        """Test text input with valid value."""
        mock_prompt.return_value = "test input"

        result = self.prompts.text_input("Enter text", "Default text")

        assert result == "test input"

    @patch("myai.cli.interactive.Prompt.ask")
    @patch("myai.cli.interactive.console")
    def test_text_input_with_validator(self, mock_console, mock_prompt):
        """Test text input with validator function."""

        def validator(text):
            return len(text) >= 3

        mock_prompt.side_effect = ["ab", "valid"]  # First invalid, then valid

        result = self.prompts.text_input("Enter text", validator=validator, error_message="Invalid input")

        assert result == "valid"
        mock_console.print.assert_any_call("[red]Invalid input[/red]")

    @patch("myai.cli.interactive.Prompt.ask")
    @patch("myai.cli.interactive.console")
    def test_text_input_with_error_message(self, mock_console, mock_prompt):
        """Test text input with custom error message."""

        def validator(text):
            return len(text) >= 3

        mock_prompt.side_effect = ["ab", "valid"]

        result = self.prompts.text_input(
            "Enter text", validator=validator, error_message="Must be at least 3 characters"
        )

        assert result == "valid"
        mock_console.print.assert_any_call("[red]Must be at least 3 characters[/red]")

    @patch("myai.cli.interactive.Confirm.ask")
    def test_confirmation_yes(self, mock_confirm):
        """Test confirmation prompt with yes response."""
        mock_confirm.return_value = True

        result = self.prompts.confirmation("Are you sure?")

        assert result is True

    @patch("myai.cli.interactive.Confirm.ask")
    def test_confirmation_no(self, mock_confirm):
        """Test confirmation prompt with no response."""
        mock_confirm.return_value = False

        result = self.prompts.confirmation("Are you sure?", default=False)

        assert result is False

    @patch("myai.cli.interactive.console")
    def test_progress_steps(self, mock_console):
        """Test progress steps display."""
        steps = ["Step 1", "Step 2", "Step 3"]

        self.prompts.progress_steps("Process Title", steps)

        # Verify console.print was called once for the panel
        assert mock_console.print.call_count == 1


class TestValidationFunctions:
    """Test cases for validation utility functions."""

    def test_validate_name_valid(self):
        """Test name validation with valid names."""
        valid_names = ["john", "john_doe", "john-doe", "john123", "john_doe_123"]

        for name in valid_names:
            assert validate_name(name), f"'{name}' should be valid"

    def test_validate_name_invalid(self):
        """Test name validation with invalid names."""
        invalid_names = [
            "",
            "john doe",  # Space
            "john@doe",  # Special char
            "john.doe",  # Period
            "123john",  # Starts with number
            "_john",  # Starts with underscore
        ]

        for name in invalid_names:
            assert not validate_name(name), f"'{name}' should be invalid"

    def test_validate_email_valid(self):
        """Test email validation with valid emails."""
        valid_emails = [
            "user@example.com",
            "user.name@example.com",
            "user+tag@example.co.uk",
            "user123@test-domain.org",
        ]

        for email in valid_emails:
            assert validate_email(email), f"'{email}' should be valid"

    def test_validate_email_invalid(self):
        """Test email validation with invalid emails."""
        invalid_emails = [
            "",
            "invalid",
            "@example.com",
            "user@",
            "user@@example.com",
            "user@.com",
            "user@example.",
        ]

        for email in invalid_emails:
            assert not validate_email(email), f"'{email}' should be invalid"

    def test_validate_url_valid(self):
        """Test URL validation with valid URLs."""
        valid_urls = [
            "https://example.com",
            "http://example.com",
            "https://example.com/path",
            "https://sub.example.com",
            "https://example.com:8080",
        ]

        for url in valid_urls:
            assert validate_url(url), f"'{url}' should be valid"

    def test_validate_url_invalid(self):
        """Test URL validation with invalid URLs."""
        invalid_urls = [
            "",
            "example.com",
            "ftp://example.com",
            "https://",
            "not-a-url",
        ]

        for url in invalid_urls:
            assert not validate_url(url), f"'{url}' should be invalid"

    def test_validate_version_valid(self):
        """Test version validation with valid versions."""
        valid_versions = [
            "1.0.0",
            "1.2.3",
            "10.20.30",
            "0.1.0",
            "1.0.0-alpha",
            "1.0.0-beta.1",
            "1.0.0-rc.1",
        ]

        for version in valid_versions:
            assert validate_version(version), f"'{version}' should be valid"

    def test_validate_version_invalid(self):
        """Test version validation with invalid versions."""
        invalid_versions = [
            "",
            "1",
            "1.0",
            "v1.0.0",
            "1.0.0.0",
            "1.0.a",
            "not-a-version",
        ]

        for version in invalid_versions:
            assert not validate_version(version), f"'{version}' should be invalid"
