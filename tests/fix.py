import pytest
import string
import subprocess
import io

from src import log

@pytest.fixture
def fix_logging():
    log.LoggerFactory.configure_test_logger()

@pytest.fixture
def fix_config(fix_logging):
    from src import config
    config_tree = {
        'heating-schedule': {
            'monday': 60,
            'tuesday': 60,
            'wednesday': 60,
            'thursday': 60,
            'friday': 60,
            'saturday': 60,
            'sunday': 60,
        },
        'fetch': {
            'url': 'https://www.nordpoolgroup.com/api/marketdata/page/10?currency=,,,EUR',
            'country_code': 'EE',
        },
        'environment': {
            'python': 'DUMMY_EXEC',
            'at_queue': 'a',
        },
        'hardware': {
            'switch_pin': 1,
            'reverse_polarity': False,
        },
        'logging': {
            'fetch_logfile': 'TEST_FETCH_LOG.log',
            'switch_logfile': 'TEST_SWITCH_LOG.log',
        }
    }
    if not config.ProgramConfig.check_config(
        config.CONFIG_REQ_KEYS, 
        config_tree):
        pytest.fail('Test configuration is missing required items!')
    return config.ProgramConfig(config_tree, 'TEST_CONFIG')

@pytest.fixture
def fix_empty_at_queue():
    at_list = io.BytesIO(subprocess.check_output(['at', '-l']))
    queues = {k: False for k in list(string.ascii_letters)}
    used_queue = None
    for line in at_list:
        queues[line.split()[6].decode('UTF-8')] = True
    for queue, in_use in queues.items():
        if not in_use:
            used_queue = queue
            break
    else:
        pytest.fail("No empty at queues to use for tests!")

    yield used_queue

    # Cleanup all commands in used queue
    at_list_after = io.BytesIO(subprocess.check_output(['at', '-l']))
    for line in at_list_after:
        if line.split()[6].decode('UTF-8') == used_queue:
            subprocess.call(['atrm', line.split()[0].decode('UTF-8')])
