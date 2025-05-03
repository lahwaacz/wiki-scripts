from pathlib import Path

import dotenv
import pytest

__all__ = [
    "docker_compose_file",
    "docker_compose_project_name",
    "docker_setup",
    "docker_cleanup",
    "containers_dotenv_values",
]


@pytest.fixture(scope="session")
def docker_compose_file(pytestconfig: pytest.Config) -> str:
    path = pytestconfig.rootpath / "tests" / "containers" / "compose.yaml"
    return str(path)


# Pin the project name to avoid creating multiple stacks
@pytest.fixture(scope="session")
def docker_compose_project_name() -> str:
    return "wiki-scripts-tests"


# Stop the stack before starting a new one
@pytest.fixture(scope="session")
def docker_setup():
    return ["down --remove-orphans --volumes", "up --build --detach"]


# Cleanup anonymous volumes created by the compose
@pytest.fixture(scope="session")
def docker_cleanup():
    return ["down --remove-orphans --volumes"]


@pytest.fixture(scope="session")
def containers_dotenv_values(docker_compose_file: str) -> dict[str, str | None]:
    dotenv_path = Path(docker_compose_file).parent / ".env"
    assert dotenv_path.is_file()
    return dotenv.dotenv_values(dotenv_path)
