import pytest
from dotenv import load_dotenv


@pytest.fixture(scope="session", autouse=True)
def load_environment_variables():
    """Load environment variables from .env file for the test session."""
    load_dotenv(".env.test", override=True)
