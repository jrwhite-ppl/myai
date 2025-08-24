"""
Agent wrapper generation for minimal integration files.

This module provides functionality to generate minimal wrapper files for Claude Code
and Cursor integrations, enabling natural conversational activation while keeping
project repositories clean.
"""

import json
import re
from typing import List

from myai.models.agent import AgentSpecification


class AgentWrapperGenerator:
    """Generate minimal agent wrappers for IDE integrations."""

    def generate_minimal_claude_wrapper(self, agent: AgentSpecification) -> str:
        """
        Generate minimal wrapper for Claude with elaborate activation description.

        Args:
            agent: The agent specification to wrap

        Returns:
            Minimal Claude-compatible markdown with activation-focused description
        """
        # Extract activation patterns from agent
        activation_phrases = self._extract_activation_phrases(agent)
        skill_keywords = self._extract_skill_keywords(agent)
        activation_scenarios = self._generate_activation_scenarios(agent)

        # Build elaborate description for natural activation
        description_parts = [
            f"{agent.metadata.display_name}.",
            f"Activates when you {activation_scenarios}",
        ]

        if activation_phrases:
            quoted_phrases = [f'"{p}"' for p in activation_phrases[:3]]
            description_parts.append(f'or say {", ".join(quoted_phrases)}')

        if skill_keywords:
            description_parts.append(f"or reference {skill_keywords}.")

        description = " ".join(description_parts)

        # Get tools or use defaults
        tools = ", ".join(agent.metadata.tools) if agent.metadata.tools else "Read, Write, Edit, Bash, Grep"

        # Generate wrapper content
        wrapper = f"""---
name: {agent.metadata.name}
description: {description}
tools: {tools}
color: "{agent.metadata.color or "#808080"}"
---

# {agent.metadata.display_name}

I'm the {agent.metadata.display_name} from MyAI. {self._extract_agent_summary(agent)}

For my complete instructions and capabilities, see:
`~/.myai/agents/{agent.metadata.category.value}/{agent.metadata.name}.md`

## Quick Activation
{self._generate_activation_examples(agent)}
"""
        return wrapper

    def generate_minimal_cursor_wrapper(self, agent: AgentSpecification) -> str:
        """
        Generate minimal MDC wrapper for Cursor.

        Args:
            agent: The agent specification to wrap

        Returns:
            Minimal Cursor-compatible MDC file with activation description
        """
        # Build activation description
        skill_summary = self._extract_skill_summary(agent)
        domain_keywords = self._extract_domain_keywords(agent)

        activation_desc = (
            f"{agent.metadata.display_name} - "
            f"Activates for {skill_summary}. "
            f"Responds to \"{agent.metadata.name}\", "
            f"\"{agent.metadata.display_name}\", "
            f"or any {domain_keywords} requests."
        )

        # Determine relevant file globs
        globs = self._determine_file_patterns(agent)

        wrapper = f"""---
description: {activation_desc}
globs: {json.dumps(globs) if globs else "[]"}
alwaysApply: false
---

# {agent.metadata.display_name} (MyAI Agent)

I help with {skill_summary}. See: ~/.myai/agents/{agent.metadata.category.value}/{agent.metadata.name}.md

Activate me by mentioning {self._extract_activation_keywords(agent)}.
"""
        return wrapper

    def _extract_activation_phrases(self, agent: AgentSpecification) -> List[str]:
        """Extract natural activation phrases from agent content."""
        phrases = []

        # Add agent name variations
        name = agent.metadata.name.replace("-", " ")
        display_name = agent.metadata.display_name

        phrases.extend(
            [
                f"Hey {name}",
                f"Hey {display_name}",
                f"Act like {display_name.lower()}",
                f"Be my {display_name.lower()}",
                f"{display_name}, help me",
            ]
        )

        # Look for phrases in content
        content_lower = agent.content.lower()
        if "i activate when" in content_lower:
            # Extract activation hints from content
            match = re.search(r"i activate when ([^.]+)", content_lower)
            if match:
                activation_text = match.group(1)
                # Extract quoted phrases
                quoted = re.findall(r'"([^"]+)"', activation_text)
                phrases.extend(quoted)

        return phrases[:5]  # Limit to 5 most relevant

    def _extract_skill_keywords(self, agent: AgentSpecification) -> str:
        """Extract skill-related keywords for activation."""
        keywords = []

        # Extract from tags
        if agent.metadata.tags:
            keywords.extend(agent.metadata.tags)

        # Extract from category
        category_keywords = {
            "engineering": ["development", "coding", "programming"],
            "business": ["analysis", "strategy", "planning"],
            "security": ["security", "vulnerability", "protection"],
            "devops": ["deployment", "infrastructure", "operations"],
            "data": ["data", "analytics", "insights"],
        }

        if agent.metadata.category.value in category_keywords:
            keywords.extend(category_keywords[agent.metadata.category.value])

        # Extract from description
        if agent.metadata.description:
            # Look for technical terms
            tech_terms = re.findall(r"\b[A-Z][a-z]+(?:[A-Z][a-z]+)*\b", agent.metadata.description)
            keywords.extend([term.lower() for term in tech_terms[:3]])

        # Return as comma-separated string
        unique_keywords = list(dict.fromkeys(keywords))  # Remove duplicates
        return ", ".join(unique_keywords[:5])

    def _generate_activation_scenarios(self, agent: AgentSpecification) -> str:
        """Generate natural language activation scenarios."""
        scenarios = []

        # Based on agent name/type
        name_lower = agent.metadata.name.lower().replace("-", " ")

        # Common patterns
        if "review" in name_lower:
            scenarios.append("need code reviewed or want feedback")
        if "python" in name_lower:
            scenarios.append("need help with Python")
        if "security" in name_lower:
            scenarios.append("have security concerns")
        if "test" in name_lower:
            scenarios.append("need testing assistance")
        if "devops" in name_lower:
            scenarios.append("need deployment or infrastructure help")
        if "lead" in name_lower or "architect" in name_lower:
            scenarios.append("need architectural guidance")

        # Generic fallback
        if not scenarios:
            scenarios.append(f"need {name_lower} expertise")

        return " or ".join(scenarios[:2])

    def _extract_agent_summary(self, agent: AgentSpecification) -> str:
        """Extract a brief summary from agent content."""
        # Look for first paragraph after identity section
        lines = agent.content.split("\n")

        for line in lines:
            if line.strip().startswith("I am") or line.strip().startswith("I'm"):
                # Found identity line, extract it
                summary = line.strip()
                # Remove "I am" or "I'm" prefix
                summary = re.sub(r"^I(?:'m| am)\s+", "", summary)
                # Capitalize first letter
                summary = summary[0].upper() + summary[1:] if summary else summary
                return summary

        # Fallback to description
        return agent.metadata.description or "I help with specialized tasks."

    def _generate_activation_examples(self, agent: AgentSpecification) -> str:
        """Generate activation examples for the agent."""
        examples = []

        # Get agent name variations
        name = agent.metadata.name.replace("-", " ")
        display_name = agent.metadata.display_name

        # Add standard examples
        examples.append(f'- "Hey {display_name}"')
        examples.append(f'- "{display_name}, help me with..."')

        # Add domain-specific examples
        if "review" in name:
            examples.append('- "Review this code"')
            examples.append('- "Check for security issues"')
        elif "python" in name:
            examples.append('- "Help me with Python"')
            examples.append('- "Debug this Python code"')
        elif "security" in name:
            examples.append('- "Analyze security risks"')
            examples.append('- "Security audit please"')
        else:
            examples.append(f'- "I need {name} help"')
            examples.append('- "' + self._generate_activation_scenarios(agent).replace(" or ", '" or "') + '"')

        return "\n".join(examples[:4])

    def _extract_skill_summary(self, agent: AgentSpecification) -> str:
        """Extract a brief skill summary for Cursor."""
        # Use description as base
        summary = agent.metadata.description or ""

        # Make it more concise
        max_length = 50
        if len(summary) > max_length:
            # Take first sentence or phrase
            summary = summary.split(".")[0]
            summary = summary.split(",")[0]

        return summary or f"{agent.metadata.display_name} tasks"

    def _extract_domain_keywords(self, agent: AgentSpecification) -> str:
        """Extract domain-specific keywords."""
        # Category-based keywords
        category_keywords = {
            "engineering": "development",
            "business": "business",
            "security": "security",
            "devops": "DevOps",
            "data": "data",
            "custom": "specialized",
        }

        domain = category_keywords.get(agent.metadata.category.value, agent.metadata.category.value)
        return f"{domain}-related"

    def _determine_file_patterns(self, agent: AgentSpecification) -> List[str]:
        """Determine relevant file glob patterns for the agent."""
        globs = []

        name_lower = agent.metadata.name.lower()

        # Language-specific patterns
        if "python" in name_lower:
            globs.extend(["**/*.py", "**/requirements.txt", "**/setup.py", "**/pyproject.toml"])
        elif "javascript" in name_lower or "typescript" in name_lower:
            globs.extend(["**/*.js", "**/*.jsx", "**/*.ts", "**/*.tsx", "**/package.json"])
        elif "java" in name_lower:
            globs.extend(["**/*.java", "**/pom.xml", "**/build.gradle"])
        elif "go" in name_lower:
            globs.extend(["**/*.go", "**/go.mod", "**/go.sum"])
        elif "rust" in name_lower:
            globs.extend(["**/*.rs", "**/Cargo.toml"])

        # Role-specific patterns
        if "test" in name_lower:
            globs.extend(["**/test/**", "**/tests/**", "**/*test*", "**/*spec*"])
        elif "config" in name_lower or "devops" in name_lower:
            globs.extend(["**/*.yml", "**/*.yaml", "**/Dockerfile", "**/*.tf"])
        elif "security" in name_lower:
            globs.extend(["**/.env*", "**/secrets/**", "**/*security*"])

        return globs

    def _extract_activation_keywords(self, agent: AgentSpecification) -> str:
        """Extract activation keywords for Cursor."""
        keywords = []

        # Add name variations
        keywords.append(agent.metadata.name.replace("-", " "))
        keywords.append(agent.metadata.display_name)

        # Add skill keywords
        if agent.metadata.tags:
            keywords.extend(agent.metadata.tags[:2])

        return ", ".join(keywords)


def get_wrapper_generator() -> AgentWrapperGenerator:
    """Get the agent wrapper generator instance."""
    return AgentWrapperGenerator()
