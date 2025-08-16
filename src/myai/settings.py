import os
import re
from typing import ClassVar, List

from pydantic_settings import BaseSettings
import requests


class Settings(BaseSettings):
    debug: bool = False


settings = Settings()  # type: ignore
