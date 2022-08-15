import sys
import os
import subprocess
import argparse
import toml

from src import config, util

def get_input(prompt):
    return input(f"{prompt}: ")

def check_python_cmd_valid(python_cmd, prompt_dict, lang):
    try:
        version_raw = subprocess.check_output([python_cmd, '-V'])
    except FileNotFoundError:
        return (False, prompt_dict['python_cmd']['invalid']['no_exist'][lang])
    version = version_raw.decode('UTF-8')
    if version.split()[0] != "Python":
        return (False, prompt_dict['python_cmd']['invalid']['not_python'][lang])
    vsplit = version.split()[1].split('.')
    if vsplit[0] != "3" or int(vsplit[1]) < 7:
        return (False, prompt_dict['python_cmd']['invalid']['version'][lang])
    return (True, None)

def get_user_weekday_minutes(prompt_dict, lang):
    weekdays = {}
    print(prompt_dict['weekdays']['prompt'][lang])
    for day in prompt_dict['weekdays']['daylist'][lang]:
        while True:
            day_in = get_input(day)
            try:
                day_num_minutes = int(day_in)
            except ValueError:
                print(prompt_dict['weekdays']['invalid'][lang], prompt_dict['try_again'][lang])
                continue
            break
        weekdays[day.lower()] = day_num_minutes
    return weekdays

def get_user_region_code(prompt_dict, lang):
    region_code = ""
    while True:
        region_code = get_input(prompt_dict['region_code']['prompt'][lang])
        check_res = config.ProgramConfig.check_config_region(region_code)
        if check_res:
            break
        print(prompt_dict['region_code']['invalid'][lang], prompt_dict['try_again'][lang])
    return region_code.upper()

def get_user_python_cmd(prompt_dict, lang):
    python_cmd = ""
    while True:
        python_cmd = get_input(prompt_dict['python_cmd']['prompt'][lang])
        valid_res = check_python_cmd_valid(python_cmd, prompt_dict, lang)
        if valid_res[0]:
            break
    return python_cmd

def get_user_relay_gpio(prompt_dict, lang):
    while True:
        gpio_pin_raw = get_input(prompt_dict['gpio']['prompt'][lang])
        try:
            gpio_pin = int(gpio_pin_raw)
        except ValueError:
            print(prompt_dict['gpio']['invalid'][lang], prompt_dict['try_again'][lang])
            continue
        return gpio_pin

def get_user_polarity(prompt_dict, lang):
    yes = prompt_dict['gpio_reverse']['answer_yes'][lang]
    no = prompt_dict['gpio_reverse']['answer_no'][lang]
    while True:
        pole_switch_raw = get_input(prompt_dict['gpio_reverse']['prompt'][lang])
        if pole_switch_raw.lower() not in (yes, no):
            print(prompt_dict['gpio_reverse']['invalid'][lang], prompt_dict['try_again'][lang])
            continue
        return pole_switch_raw.lower() == yes

def get_user_logfile(prompt_dict, lang):
    pass

def create_new_conf(prompt_dict, lang):
    conf = {
        'fetch': {},
        'environment': {},
        'hardware': {},
        'logging': {},
    }

    conf['heating-schedule'] = get_user_weekday_minutes(prompt_dict, lang)
    conf['fetch']['url'] = "https://www.nordpoolgroup.com/api/marketdata/page/10?currency=,,,EUR"
    conf['fetch']['region_code'] = get_user_region_code(prompt_dict, lang)

    if sys.version_info.major == 3 and sys.version_info.minor >= 7:
        conf['environment']['python'] = os.path.realpath(sys.executable)
    else:
        print(prompt_dict['python_cmd']['auto_fail'][lang])
        conf['environment']['python'] = get_user_python_cmd(prompt_dict, lang)

    conf['environment']['at_queue'] = 'a'
    conf['hardware']['switch_pin'] = get_user_relay_gpio(prompt_dict, lang)
    conf['hardware']['reverse_polarity'] = get_user_polarity(prompt_dict, lang)
    conf['logging']['fetch_logfile'] = "fetch.log"
    conf['logging']['switch_logfile'] = "switch.log"

    # Validate new configuration just to be sure
    if not config.ProgramConfig.check_config(conf):
        util.exit_critical_bare("Something wen't wrong with the configuration! Try again!")

    return config.ProgramConfig(conf, "default_config.toml")

def amend_existing_conf(conf):
    pass

def get_user_language():
    while True:
        for i, lang_option in enumerate(langfile['lang_choices'].values()):
            print(f"{i + 1}. {lang_option}")
        selection = get_input("Select langauge option")

        try:
            select_int = int(selection)
            return list(langfile['lang_choices'].keys())[select_int - 1]
        except ValueError:
            pass
        
        for lang_key, lang_option in langfile['lang_choices'].items():
            if selection.lower() == lang_option.lower():
                return lang_key

        print("Bad selection. Try again.")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--configfile', nargs=1, default=None,
                        help="Configration file path to amend.")
    args = parser.parse_args()

    try:
        langfile: dict = toml.load("data/prompts.toml")
    except FileNotFoundError:
        util.exit_critical_bare("Couldn't find prompt file!")

    lang = get_user_language()

    print(langfile['greeting'][lang])
    if args.configfile:
        conf = config.ProgramConfig.from_file(args.configfile)
        amend_existing_conf(conf)
    else:
        conf = create_new_conf(langfile, lang)
        print(conf)

    newpath = get_input(langfile['save_config']['prompt'])
    if not newpath:
        # User chose to reuse previous path or default
        newpath = conf.source_file
    toml.dump(conf, newpath)
