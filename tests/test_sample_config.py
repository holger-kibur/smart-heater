
from src import config

def test_sample_config():
    config.ProgramConfig.from_file('sample_conf.toml')
