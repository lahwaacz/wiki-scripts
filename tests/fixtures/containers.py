from pathlib import Path

import dotenv
import pytest

__all__ = [
    "pytest_addoption",
    "keep_containers_running",
    "docker_compose_file",
    "docker_compose_project_name",
    "docker_setup",
    "docker_cleanup",
    "containers_dotenv_values",
]


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--keep-containers-running",
        action="store_true",
        help="Keep containers running after the test (i.e. don't run `docker compose down`).",
    )


@pytest.fixture(scope="session")
def keep_containers_running(request: pytest.FixtureRequest) -> bool:
    """
    Bool fixture determining whether to keep containers running after the test
    (i.e. don't run `docker compose down`).
    """
    value = request.config.getoption("--keep-containers-running")
    return bool(value)


@pytest.fixture(scope="session")
def docker_compose_file(pytestconfig: pytest.Config) -> str:
    path = pytestconfig.rootpath / "tests" / "containers" / "compose.yaml"
    return str(path)


@pytest.fixture(
    scope="session",
    # this trick adds a marker to all tests using the fixture
    params=[pytest.param(None, marks=pytest.mark.containers)],
)
def docker_compose_project_name() -> str:
    """Return a project name for using docker compose."""
    # Pin the project name to avoid creating multiple stacks
    return "wiki-scripts-tests"


@pytest.fixture(scope="session")
def docker_setup(keep_containers_running: bool) -> list[str]:
    """Spin up containers for the pytest session using docker compose."""
    if keep_containers_running:
        return ["up --build --detach"]
    return ["down --remove-orphans --volumes", "up --build --detach"]


@pytest.fixture(scope="session")
def docker_cleanup(keep_containers_running: bool) -> list[str]:
    """Tear down containers for the pytest session using docker compose."""
    if keep_containers_running:
        return []
    return ["down --remove-orphans --volumes"]


@pytest.fixture(scope="session")
def containers_dotenv_values(docker_compose_file: str) -> dict[str, str | None]:
    """Return a dict of environment variables configured in the `.env` file of the compose project."""
    dotenv_path = Path(docker_compose_file).parent / ".env"
    assert dotenv_path.is_file()
    return dotenv.dotenv_values(dotenv_path)
