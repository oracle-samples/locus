# Contributing to Locus

Thank you for your interest in contributing to Locus! This document provides guidelines and instructions for contributing.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Making Changes](#making-changes)
- [Pull Request Process](#pull-request-process)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Documentation](#documentation)

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](https://www.contributor-covenant.org/version/2/1/code_of_conduct/). By participating, you agree to uphold this code.

## Getting Started

### Oracle Contributor Agreement (OCA)

Before contributing code, you must sign the [Oracle Contributor Agreement (OCA)](https://oca.opensource.oracle.com). This is required for all contributions.

All commits must include a sign-off line:

```text
Signed-off-by: Your Name <your.email@example.com>
```

Use `git commit --signoff` or `git commit -s` to add this automatically.

### Types of Contributions

We welcome:

- **Bug fixes** - Fix issues and improve stability
- **Features** - New capabilities aligned with the roadmap
- **Documentation** - Tutorials, examples, API docs
- **Tests** - Unit tests, integration tests, benchmarks
- **Performance** - Optimizations and efficiency improvements

## Development Setup

### Prerequisites

- Python 3.11 or higher
- [Hatch](https://hatch.pypa.io/) for project management
- Git

### Installation

```bash
# Clone the repository
git clone https://github.com/oracle-samples/locus.git
cd locus

# Install Hatch if needed
pip install hatch

# Create development environment
hatch env create

# Install pre-commit hooks
hatch run pre-commit install

# Verify setup
hatch run test
```

### Environment Variables

For integration tests, configure these environment variables:

```bash
# OCI GenAI (required for most integration tests). The transport is
# picked automatically per model id — cohere.command-r-* uses OCIModel
# (SDK), everything else uses OCIOpenAIModel (/openai/v1). Set
# LOCUS_OCI_TRANSPORT=v1|sdk to override. See docs/how-to/oci-models.md.
export OCI_PROFILE="DEFAULT"
export OCI_REGION="us-chicago-1"
export OCI_MODEL_ID="openai.gpt-5.5"   # → OCIOpenAIModel (V1)

# Only needed when OCI_MODEL_ID is a Cohere R-series model — OCIModel
# (SDK transport) reads OCI_AUTH_TYPE / OCI_ENDPOINT / OCI_COMPARTMENT:
# export OCI_MODEL_ID="cohere.command-r-plus-08-2024"
# export OCI_AUTH_TYPE="api_key"
# export OCI_ENDPOINT="https://inference.generativeai.us-chicago-1.oci.oraclecloud.com"
# export OCI_COMPARTMENT="ocid1.compartment.oc1..your-compartment-id"

# OpenAI (optional, for OpenAI provider tests)
export OPENAI_API_KEY="sk-..."

# Anthropic (optional, for Anthropic provider tests)
export ANTHROPIC_API_KEY="sk-ant-..."

# Ollama (optional, for local LLM tests)
export OLLAMA_AVAILABLE="1"
export OLLAMA_MODEL="llama3.2"

# Docker services (for checkpoint/vector store tests)
export REDIS_URL="redis://localhost:6379"
export POSTGRES_HOST="localhost"
export POSTGRES_PORT="5432"
export POSTGRES_USER="postgres"
export POSTGRES_PASSWORD="postgres"
export POSTGRES_DB="locus"
export QDRANT_HOST="localhost"
export QDRANT_PORT="6333"
```

## Making Changes

### Branch Naming

Use descriptive branch names:

```
feat/add-pinecone-store
fix/memory-leak-in-checkpointer
docs/rag-tutorial-improvements
test/add-swarm-integration-tests
```

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]

[optional footer]
Signed-off-by: Your Name <email>
```

Types:

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `test`: Tests
- `refactor`: Code refactoring
- `perf`: Performance improvement
- `ci`: CI/CD changes
- `chore`: Maintenance

Examples:

```bash
git commit -s -m "feat(rag): add Pinecone vector store support"
git commit -s -m "fix(memory): resolve checkpoint corruption on concurrent writes"
git commit -s -m "docs(tutorials): add RAG with Oracle 26ai example"
```

### Code Changes

1. **Create a branch** from `main`:

   ```bash
   git checkout -b feat/my-feature
   ```

2. **Make changes** following coding standards

3. **Run checks** before committing:

   ```bash
   hatch run lint      # Ruff + mypy
   hatch run test      # Unit tests
   hatch run fmt       # Auto-format code
   ```

4. **Commit** with sign-off:

   ```bash
   git commit -s -m "feat: add my feature"
   ```

5. **Push** to your fork:

   ```bash
   git push origin feat/my-feature
   ```

## Pull Request Process

1. **Create an issue** first to discuss the change

2. **Open a PR** with:
   - Clear title following Conventional Commits
   - Description of changes
   - Link to related issue
   - Test results

3. **PR Template**:

   ```markdown
   ## Summary
   Brief description of changes.

   ## Related Issue
   Fixes #123

   ## Changes
   - Added X
   - Fixed Y
   - Updated Z

   ## Testing
   - [ ] Unit tests pass
   - [ ] Integration tests pass (if applicable)
   - [ ] Manual testing performed

   ## Checklist
   - [ ] Code follows project style
   - [ ] Tests added/updated
   - [ ] Documentation updated
   - [ ] Commits are signed off
   ```

4. **Review process**:
   - Maintainers will review within 1 week
   - Address feedback promptly
   - Squash commits if requested

## Coding Standards

### Python Style

- **Formatter**: Ruff (line length: 100)
- **Linter**: Ruff + mypy (strict mode)
- **Type hints**: Required for all public APIs
- **Docstrings**: Google style

```python
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from locus.core.state import AgentState


class MyConfig(BaseModel):
    """Configuration for MyComponent.

    Attributes:
        name: The component name.
        max_retries: Maximum retry attempts.
    """

    name: str = Field(description="Component name")
    max_retries: int = Field(default=3, ge=1, le=10)


async def process_state(state: "AgentState", config: MyConfig) -> "AgentState":
    """Process the agent state.

    Args:
        state: Current agent state.
        config: Processing configuration.

    Returns:
        Updated agent state.

    Raises:
        ValueError: If state is invalid.
    """
    if not state.messages:
        raise ValueError("State must have messages")

    # Processing logic here
    return state.with_metadata({"processed": True})
```

### Architecture Guidelines

1. **Pydantic-first**: Use Pydantic models for all data structures
2. **Immutable state**: Use frozen models, return new instances
3. **Async-native**: Prefer async functions
4. **Protocol-based**: Define interfaces with `typing.Protocol`
5. **No magic**: Explicit over implicit

### File Organization

```
src/locus/
├── __init__.py          # Public exports
├── module/
│   ├── __init__.py      # Module exports
│   ├── base.py          # Base classes/protocols
│   ├── impl.py          # Implementations
│   └── utils.py         # Utilities
```

## Testing

### Running Tests

```bash
# All unit tests
hatch run test

# Specific test file
hatch run pytest tests/unit/test_agent.py -v

# With coverage
hatch run test-cov

# Integration tests (requires services)
hatch run pytest tests/integration -v

# Specific marker
hatch run pytest -m "requires_oci" -v
```

### Writing Tests

```python
import pytest
from locus import Agent
from locus.core.messages import Message


class TestAgent:
    """Tests for Agent class."""

    @pytest.fixture
    def mock_model(self, mocker):
        """Create a mock model."""
        model = mocker.MagicMock()
        model.complete = mocker.AsyncMock(return_value=...)
        return model

    @pytest.mark.asyncio
    async def test_agent_runs_successfully(self, mock_model):
        """Agent should complete a simple task."""
        agent = Agent(model=mock_model)

        result = await agent.run("Hello")

        assert result.success
        assert result.message is not None

    @pytest.mark.asyncio
    async def test_agent_handles_tool_error(self, mock_model):
        """Agent should handle tool execution errors gracefully."""
        # Test implementation
        pass
```

### Test Categories

- `tests/unit/` - Unit tests (no external dependencies)
- `tests/integration/` - Integration tests (require services)
- Markers: `@pytest.mark.requires_oci`, `@pytest.mark.requires_redis`, etc.

## Documentation

### Code Documentation

- All public functions/classes need docstrings
- Use Google-style docstrings
- Include type hints
- Add examples for complex APIs

### Tutorials

When adding tutorials to `examples/`:

1. Follow naming: `XX_topic_name.py`
2. Include header comment explaining the tutorial
3. Use clear, educational code
4. Test that it runs successfully

### README Updates

For significant features, update:

- Feature matrix in `docs/FEATURES.md`
- Quick Start examples in `README.md` (only if the feature changes the
  five-things-that-make-Locus-different shape)
- Architecture section in `README.md` (if a new top-level module)

## Release checklist

Every release follows this checklist. Do not skip steps.

1. **Update `CHANGELOG.md`.** Move the relevant entries from
   `[Unreleased]` into a new version heading. Write the date in
   `YYYY-MM-DD`. Add `### Removed` / `### Changed` notes for anything
   breaking, with a migration snippet.
2. **Deprecation sweep.** For every item in `[Unreleased] > Removed`,
   confirm a `LocusDeprecationWarning` has been in place for at least
   one prior minor release, or document the single-release migration
   path in the CHANGELOG entry.
3. **Version bump.** Update `__version__` in `src/locus/__init__.py`
   and the `version` field in `pyproject.toml`.
4. **Run the full matrix.** `hatch run all` locally plus
   `pytest tests/integration/ -v` with live services available.
5. **Tag.** `git tag -a v<version> -m 'Release v<version>'` and push
   the tag.
6. **Publish.** Build the wheel (`hatch build`), verify the wheel
   contents do not include compliance artifacts or test data, then
   upload.
7. **Announce.** CHANGELOG entry ships with the release notes; any
   deprecations are called out again in the release announcement.

See [`DEPRECATION.md`](DEPRECATION.md) for the full deprecation policy
and how `LocusDeprecationWarning` works.

## Questions?

- Open a [GitHub Discussion](https://github.com/oracle-samples/locus/discussions)
- Check existing [Issues](https://github.com/oracle-samples/locus/issues)

Thank you for contributing to Locus!
