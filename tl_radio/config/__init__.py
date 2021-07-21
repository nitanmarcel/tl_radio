import os
from typing import Union

from omegaconf import OmegaConf, DictConfig
from ruamel.yaml import YAML

import tl_radio
from .base import BaseConfig


class Config:
    def __init__(self, config_path: str = "config.yaml"):
        self.example_config: str = os.path.join(self.base_path, "example_config.yaml")
        self.config_path: str = config_path

    def generate(self):
        with open(self.example_config, "r") as base_yaml:
            with open(self.config_path, "w+") as config_yaml:
                config_yaml.write(base_yaml.read())

    def load(self) -> Union[BaseConfig, DictConfig]:
        if self.exists:
            self.update()
        return OmegaConf.load(self.config_path)

    def update(self):
        yaml = YAML()
        yaml.preserve_quotes = True
        yaml.indent(mapping=4, sequence=4, offset=2)
        with open(self.example_config, "r") as conf:
            base = yaml.load(conf)
        with open(self.config_path, "r") as conf:
            config = yaml.load(conf)

        for k, v in config.items():
            base[k].update(v)
        with open(self.config_path, "w") as new_yaml:
            yaml.dump(base, new_yaml)

    @property
    def exists(self) -> bool:
        return os.path.isfile(self.config_path)

    @property
    def base_path(self):
        return tl_radio.__path__[0]
