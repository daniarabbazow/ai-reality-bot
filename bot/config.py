import os
from dataclasses import dataclass

from dotenv import load_dotenv


class ConfigError(Exception):
    pass


@dataclass
class Config:
    bot_token: str


def load_config() -> Config:
    load_dotenv()
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise ConfigError(
            "BOT_TOKEN не задан. Скопируй .env.example в .env и впиши туда токен бота."
        )
    return Config(bot_token=token)
