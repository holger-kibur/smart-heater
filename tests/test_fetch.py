import subprocess
import io


def test_fetch(fix_config, fix_empty_at_queue):
    print('Using queue', fix_empty_at_queue)

    from src import fetch

    # Configure test so it interferes as little as possible
    fix_config['environment']['at_queue'] = fix_empty_at_queue

    fetch.do_fetch(prog_config=fix_config)

    # Inspect at queue to see if commands were entered correctly
    at_queue = io.BytesIO(subprocess.check_output(['at', '-l']))

    num_in_queue = 0
    for sched_cmd in at_queue:
        if sched_cmd.split()[6].decode('UTF-8') == fix_empty_at_queue:
            num_in_queue += 1

    assert num_in_queue >= 0, "Fetch didn't put any commands in at queue!"
    assert num_in_queue % 2 == 0, "Fetch put an uneven number of commands in at queue!"


