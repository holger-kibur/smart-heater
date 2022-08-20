import sys
import os
import subprocess
import argparse
import toml

from src import config, util, manage

class PromptCollection():
    GLOB_LANGFILE = None
    GLOB_LANG = None
    
    @classmethod
    def config_pc(cls, langfile, lang):
        cls.GLOB_LANGFILE = langfile
        cls.GLOB_LANG = lang

    @classmethod
    def _toplevel(cls, key):
        if cls.GLOB_LANGFILE is not None:
            return cls.GLOB_LANGFILE[key][cls.GLOB_LANG]
        raise Exception("PromptCollection needs to be configured prior!")

    @classmethod
    def greeting(cls):
        return cls._toplevel('greeting')

    @classmethod
    def amend(cls):
        return cls._toplevel('amend')

    def __init__(self, section):
        if self.GLOB_LANGFILE is not None and self.GLOB_LANG is not None:
            self.root = self.GLOB_LANGFILE[section]
        else:
            util.exit_critical_bare("Tried to instantiate PromptCollection before the class was configured!")

    def prompt(self):
        return self.root['prompt'][self.GLOB_LANG]

    def try_again(self, subkey=None):
        # This check is unneccesary since it's impossible to instantiate
        # PromptCollection without it being configured, but we need to placate
        # static analysis `\_('',)_/^.
        if self.GLOB_LANGFILE is not None and self.GLOB_LANG is not None:
            return self.invalid(subkey) + self.GLOB_LANGFILE['try_again'][self.GLOB_LANG]

    def invalid(self, subkey=None):
        pre = self.root['invalid']
        if subkey is not None:
            pre = pre[subkey]
        return pre[self.GLOB_LANG]

    def label(self):
        return self.root['label'][self.GLOB_LANG]
    
    def __getitem__(self, key):
        return self.root[key][self.GLOB_LANG]

def get_input(prompt):
    return input(f"{prompt}: ")

def get_yes_no(prompt):
    pc = PromptCollection('yesno')
    yes = pc['yes']
    no = pc['no']
    while True:
        ans = input(f"{prompt} ({yes}/{no}): ")
        if ans.lower() not in (yes, no):
            print(pc.invalid())
            continue
        return ans.lower() == yes

def check_python_cmd_valid(python_cmd):
    try:
        version_raw = subprocess.check_output([python_cmd, '-V'])
    except FileNotFoundError:
        return (False, 'no_exist')
    version = version_raw.decode('UTF-8')
    if version.split()[0] != "Python":
        return (False, 'not_python')
    vsplit = version.split()[1].split('.')
    if vsplit[0] != "3" or int(vsplit[1]) < 7:
        return (False, 'version')
    return (True, None)

def get_user_weekday_minutes():
    pc = PromptCollection('weekdays')
    weekdays = {}
    print(pc.prompt())
    for i, day in enumerate(pc['daylist']):
        while True:
            day_in = get_input(day)
            try:
                day_num_minutes = int(day_in)
            except ValueError:
                print(pc.try_again())
                continue
            break
        print(config.WEEKDAY_KEYS[i])
        weekdays[config.WEEKDAY_KEYS[i]] = day_num_minutes
    return weekdays

def get_user_region_code():
    pc = PromptCollection('region_code')
    region_code = ""
    while True:
        region_code = get_input(pc.prompt())
        check_res = config.ProgramConfig.check_config_region(region_code)
        if check_res:
            break
        print(pc.try_again())
    return region_code.upper()

def get_user_python_cmd():
    pc = PromptCollection('python_cmd')
    python_cmd = ""
    while True:
        python_cmd = get_input(pc.prompt())
        valid_res = check_python_cmd_valid(python_cmd)
        if valid_res[0]:
            break
        print(pc.try_again(subkey=valid_res[1]))
    return python_cmd

def get_user_relay_gpio():
    pc = PromptCollection('gpio')
    while True:
        gpio_pin_raw = get_input(pc.prompt())
        try:
            gpio_pin = int(gpio_pin_raw)
        except ValueError:
            print(pc.try_again())
            continue
        return gpio_pin

def get_user_polarity():
    pc = PromptCollection('gpio_reverse')
    return get_yes_no(pc.prompt())

def get_user_logfile():
    pass

def create_new_conf():
    conf = {
        'fetch': {},
        'environment': {},
        'hardware': {},
        'logging': {},
    }

    conf['heating-schedule'] = get_user_weekday_minutes()
    conf['fetch']['url'] = "https://www.nordpoolgroup.com/api/marketdata/page/10?currency=,,,EUR"
    conf['fetch']['region_code'] = get_user_region_code()

    if sys.version_info.major == 3 and sys.version_info.minor >= 7:
        conf['environment']['python'] = os.path.realpath(sys.executable)
    else:
        print(PromptCollection('python_cmd')['auto_fail'])
        conf['environment']['python'] = get_user_python_cmd()

    conf['environment']['switch_queue'] = 's'
    conf['hardware']['switch_pin'] = get_user_relay_gpio()
    conf['hardware']['reverse_polarity'] = get_user_polarity()
    conf['logging']['fetch_logfile'] = "fetch.log"
    conf['logging']['switch_logfile'] = "switch.log"

    # Validate new configuration just to be sure
    conf_check = config.ProgramConfig.check_config(conf)
    if not conf_check[0]:
        util.exit_critical_bare(f"Something wen't wrong with the configuration! Try again!\nReason: {conf_check[1]}")

    return config.ProgramConfig(conf, "default_config.toml")

def user_amend_field(langkey, change_func):
    pc = PromptCollection(langkey)
    if get_yes_no(f"{PromptCollection.amend()} {pc.label()}"):
        return change_func()
    return None

def amend_existing_conf(conf):
    temp = user_amend_field('weekdays', get_user_weekday_minutes)
    if temp is not None:
        conf['heating-schedule'] = temp

    temp = user_amend_field('region_code', get_user_region_code)
    if temp is not None:
        conf['fetch']['region_code'] = temp

    temp = user_amend_field('gpio', get_user_relay_gpio)
    if temp is not None:
        conf['hardware']['switch_pin'] = temp

    temp = user_amend_field('gpio_reverse', get_user_polarity)
    if temp is not None:
        conf['hardware']['reverse_polarity'] = temp

    # Validate amended configuration just to be sure
    conf_check = config.ProgramConfig.check_config(conf.config_tree)
    if not conf_check[0]:
        util.exit_critical_bare(f"Something wen't wrong with amending the configuration! Try again!\nReason: {conf_check[1]}")

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

def user_save_file(conf):
    pc = PromptCollection('save_config')
    newpath = get_input(pc.prompt())
    if not newpath:
        # User chose to reuse previous path or default
        newpath = conf.source_file
    else:
        newpath += '.toml'
    print(newpath)
    with open(newpath, 'w') as conf_file:
        toml.dump(conf.config_tree, conf_file)
    conf.source_file = newpath

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
    PromptCollection.config_pc(langfile, lang)

    print(PromptCollection.greeting())
    if args.configfile:
        conf = config.ProgramConfig.from_file(args.configfile[0])
        old_switch_queue = conf['environment']['switch_queue']
        amend_existing_conf(conf)
    else:
        conf = create_new_conf()
        old_switch_queue = None
        print(conf)

    user_save_file(conf)

    # (Re)set fetch cronjob
    manage.CronWrapper.clear_fetch_cronjob()
    manage.CronWrapper.add_fetch_cronjob(conf)

    # (Re)set switch atjobs
    # Scheduled times for already queued will not change, but their
    # configuration filepaths will.
    at = manage.AtWrapper
    if old_switch_queue is not None:
        with at.queue_pidfile():
            for i, sched_switch in enumerate(at.queue_filter(
                    at.get_at_queue_members(),
                    old_switch_queue)):
                at.remove_member(sched_switch)
                at.add_switch_command(
                        conf,
                        'OFF' if i % 2 == 0 else 'ON',
                        sched_switch.dt)

