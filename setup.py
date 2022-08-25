"""
Script for conveniently creating a working configuration and setting up
crontab, atjobs. It can also be used to amend an existing configuration.
"""
from __future__ import annotations

import sys
import os
import subprocess
import argparse
from typing import Optional, Callable, TypeVar
import toml

from src import config, util, manage

T = TypeVar("T")


class PromptCollection:
    """
    Utility class for using language information from the language TOML data
    file.

    This class--once configured--allows for convenient access to prompts from
    the language file, without having to specify the language it should be in.
    It also provides some shorthand methods for common fields.

    Class methods:
        config_pc
        greeting
        amend

    Instance methods:
        prompt
        try_again
        invalid
        label
    """

    GLOB_LANGFILE: Optional[dict] = None
    GLOB_LANG: Optional[str] = None

    @classmethod
    def config_pc(cls, langfile: dict, lang: str):
        """
        Configure the class with the loaded language file, plus the chosen
        language.
        """
        cls.GLOB_LANGFILE = langfile
        cls.GLOB_LANG = lang

    @classmethod
    def _toplevel(cls, key: str) -> str:
        """
        Get the language-specific toplevel language file field.

        @param key Language file field name.

        @return Language-specific field content,
        """
        if cls.GLOB_LANGFILE is not None:
            return cls.GLOB_LANGFILE[key][cls.GLOB_LANG]
        raise Exception("PromptCollection needs to be configured prior!")

    @classmethod
    def greeting(cls) -> str:
        """
        Get the language-specific greeting.

        @return Language-specific greeting.
        """
        return cls._toplevel("greeting")

    @classmethod
    def amend(cls) -> str:
        """
        Get the langauge-specific configuration field amend prompt.

        @return Language-specific amend prompt.
        """
        return cls._toplevel("amend")

    def __init__(self, section: str):
        if self.GLOB_LANGFILE is not None and self.GLOB_LANG is not None:
            self.root = self.GLOB_LANGFILE[section]
        else:
            util.exit_critical_bare(
                "Tried to instantiate PromptCollection before the class was configured!"
            )

    def prompt(self) -> str:
        """
        Get the section prompt.

        @return Section prompt.
        """
        return self.root["prompt"][self.GLOB_LANG]

    def try_again(self, subkey: Optional[str] = None) -> str:
        """
        Get the section try again message.

        @return Section try again message.
        """
        return self.invalid(subkey) + self._toplevel("try_again")

    def invalid(self, subkey: Optional[str] = None) -> str:
        """
        Get the section invalid message.

        @return Section invalid message.
        """
        pre = self.root["invalid"]
        if subkey is not None:
            pre = pre[subkey]
        return pre[self.GLOB_LANG]

    def label(self) -> str:
        """
        Get the section label.

        @return Section label.
        """
        return self.root["label"][self.GLOB_LANG]

    def __getitem__(self, key):
        return self.root[key][self.GLOB_LANG]


def get_input(prompt: str) -> str:
    """
    Prompt the user for a generic response.

    @param Message to prompt the user with.

    @return The generic response.
    """

    return input(f"{prompt}: ")


def get_yes_no(prompt: str) -> bool:
    """
    Prompt user with a yes/no question, to which the user needs to respond with
    the configured language specific yes or no options.

    @prompt Message to prompt the user with.

    @return User response (True is a positive response).
    """

    pc = PromptCollection("yesno")
    yes = pc["yes"]
    no = pc["no"]
    while True:
        ans = input(f"{prompt} ({yes}/{no}): ")
        if ans.lower() not in (yes, no):
            print(pc.invalid())
            continue
        return ans.lower() == yes


def check_python_cmd_valid(python_cmd: str) -> tuple[bool, Optional[str]]:
    """
    Check if a python command/executable is satisfactory for smart-heater
    scripts. Give a helpful reason in case it isn't.

    @param python_cmd String containing a python exeutable or command to be
    executed in a shell environment.

    @return Validity (0th) and optional reason (1st) in case it isn't.
    """
    try:
        version_raw = subprocess.check_output([python_cmd, "-V"])
    except FileNotFoundError:
        return (False, "no_exist")
    version = version_raw.decode("UTF-8")
    if version.split()[0] != "Python":
        return (False, "not_python")
    vsplit = version.split()[1].split(".")
    if vsplit[0] != "3" or int(vsplit[1]) < 7:
        return (False, "version")
    return (True, None)


def get_user_weekday_minutes() -> dict:
    """
    Construct a minutes-per-weekday mapping from user input.

    @return Heating ninutes per weekday mapping.
    """
    pc = PromptCollection("weekdays")
    weekdays = {}
    print(pc.prompt())
    for i, day in enumerate(pc["daylist"]):
        while True:
            day_in = get_input(day)
            try:
                day_num_minutes = int(day_in)
            except ValueError:
                print(pc.try_again())
                continue
            break
        weekdays[config.WEEKDAY_KEYS[i]] = day_num_minutes
    return weekdays


def get_user_region_code() -> str:
    """
    Get a valid region code from the user.

    @return Uppercase Nordpool-conforming region.
    """
    pc = PromptCollection("region_code")
    region_code = ""
    while True:
        region_code = get_input(pc.prompt())
        check_res = config.ProgramConfig.check_config_region(region_code)
        if check_res:
            break
        print(pc.try_again())
    return region_code.upper()


def get_user_python_cmd() -> str:
    """
    Get a valid python command/executable from the user that can be used to
    execute smart heater scripts.

    @return The executable path/command
    """
    pc = PromptCollection("python_cmd")
    python_cmd = ""
    while True:
        python_cmd = get_input(pc.prompt())
        valid_res = check_python_cmd_valid(python_cmd)
        if valid_res[0]:
            break
        print(pc.try_again(subkey=valid_res[1]))
    return python_cmd


def get_user_relay_gpio() -> int:
    """
    Get a GPIO pin from the user. This is not currently checked for validity.

    @return The BCM mode GPIO number.
    """
    pc = PromptCollection("gpio")
    while True:
        gpio_pin_raw = get_input(pc.prompt())
        try:
            gpio_pin = int(gpio_pin_raw)
        except ValueError:
            print(pc.try_again())
            continue
        return gpio_pin


def get_user_polarity() -> bool:
    """
    Get the user's input for whether we should operate in reverse-polarity.

    @return True == reverse, False == normal.
    """
    pc = PromptCollection("gpio_reverse")
    return get_yes_no(pc.prompt())


def create_new_conf() -> config.ProgramConfig:
    """
    Create a new ProgramConfig with user input.

    This function hardcodes some configuration fields that can be reasonably
    assumed to be constant across different users. The purpose of this is to
    hide implementation details from the user.

    @return A validated ProgramConfig.
    """

    conf = {
        "fetch": {},
        "environment": {},
        "hardware": {},
        "logging": {},
    }

    conf["heating-schedule"] = get_user_weekday_minutes()
    conf["fetch"][
        "url"
    ] = "https://www.nordpoolgroup.com/api/marketdata/page/10?currency=,,,EUR"
    conf["fetch"]["region_code"] = get_user_region_code()

    if sys.version_info.major == 3 and sys.version_info.minor >= 7:
        conf["environment"]["python"] = os.path.realpath(sys.executable)
    else:
        print(PromptCollection("python_cmd")["auto_fail"])
        conf["environment"]["python"] = get_user_python_cmd()

    conf["environment"]["switch_queue"] = "s"
    conf["environment"]["script_dir"] = os.getcwd()
    conf["hardware"]["switch_pin"] = get_user_relay_gpio()
    conf["hardware"]["reverse_polarity"] = get_user_polarity()
    conf["logging"]["fetch_logfile"] = f"{os.getcwd()}/fetch.log"
    conf["logging"]["switch_logfile"] = f"{os.getcwd()}/switch.log"

    # Validate new configuration just to be sure
    conf_check = config.ProgramConfig.check_config(conf)
    if not conf_check[0]:
        util.exit_critical_bare(
            f"Something wen't wrong with the configuration! Try again!\nReason: {conf_check[1]}"
        )

    return config.ProgramConfig(conf, config.CONFIG_FOLDER + "default_config.toml")


def user_amend_field(langkey: str, change_func: Callable[[], T]) -> Optional[T]:
    """
    Wrapper function to allow the user to choose whether they want to amend a
    configuration field.

    @param langkey Which langfile section this configuration field corresponds
    to. This is used to display the section label in the amendment prompt.

    @param change_func The function that should be used to get the new value of
    the configuration field. This should be one of the get_user_* functions
    used in create_new_conf.

    @return None if user chose not to amend, or the return value of the passed
    get_user_* function othweise.
    """

    pc = PromptCollection(langkey)
    if get_yes_no(f"{PromptCollection.amend()} {pc.label()}"):
        return change_func()
    return None


def amend_existing_conf(conf: config.ProgramConfig):
    """
    Amend an existing valid configuration, giving the user the option for
    whether or not to amend each field.

    This function assumes that the stored python executable/command is already
    valid, and therefore doesn't need to be amended.

    @param conf The ProgramConfig instance to-be-amended.
    """

    temp = user_amend_field("weekdays", get_user_weekday_minutes)
    if temp is not None:
        conf["heating-schedule"] = temp

    temp = user_amend_field("region_code", get_user_region_code)
    if temp is not None:
        conf["fetch"]["region_code"] = temp

    temp = user_amend_field("gpio", get_user_relay_gpio)
    if temp is not None:
        conf["hardware"]["switch_pin"] = temp

    temp = user_amend_field("gpio_reverse", get_user_polarity)
    if temp is not None:
        conf["hardware"]["reverse_polarity"] = temp

    # Validate amended configuration just to be sure
    conf_check = config.ProgramConfig.check_config(conf.config_tree)
    if not conf_check[0]:
        util.exit_critical_bare(
            "Something wen't wrong with amending the configuration! Try again!\nReason: {}".format(
                conf_check[1]
            )
        )


def get_user_language(langfile: dict) -> str:
    """
    Get user language choice.

    @param langfile The parsed TOML language file.

    @return The key for the language the user chose. This can be directly used
    to configure PromptCollection.
    """

    while True:
        for i, lang_option in enumerate(langfile["lang_choices"].values()):
            print(f"{i + 1}. {lang_option}")
        selection = get_input("Select langauge option")

        try:
            select_int = int(selection)
            return list(langfile["lang_choices"].keys())[select_int - 1]
        except ValueError:
            pass

        for lang_key, lang_option in langfile["lang_choices"].items():
            if selection.lower() == lang_option.lower():
                return lang_key

        print("Bad selection. Try again.")


def user_save_file(conf: config.ProgramConfig):
    """
    Get user input for the new configuration filepath (if desired) and save the
    passed configuration.

    This function will append '.toml' to the end of the user's input.

    @param conf The configuration to-be-saved.
    """

    pc = PromptCollection("save_config")
    newpath = get_input(pc.prompt())

    if not newpath:
        # User chose to reuse previous path or default
        newpath = conf.source_file
    elif not os.path.isabs(newpath):
        newpath = config.CONFIG_FOLDER + newpath + ".toml"

    os.makedirs(os.path.dirname(newpath), exist_ok=True)
    with open(newpath, "w", encoding="UTF-8") as conf_file:
        toml.dump(conf.config_tree, conf_file)
    conf.source_file = newpath


def do_setup(args: argparse.Namespace):
    """
    Main function for setup logic.

    @parma args Parsed command line arguments.
    """

    try:
        langfile: dict = toml.load("data/prompts.toml")
    except FileNotFoundError:
        util.exit_critical_bare("Couldn't find prompt file!")
    lang = get_user_language(langfile)
    PromptCollection.config_pc(langfile, lang)

    print(PromptCollection.greeting())
    if args.configfile:
        conf = config.ProgramConfig.from_file(args.configfile[0])
        old_switch_queue = conf["environment"]["switch_queue"]
        amend_existing_conf(conf)
    else:
        conf = create_new_conf()
        old_switch_queue = None
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
            for i, sched_switch in enumerate(
                at.queue_filter(at.get_at_queue_members(), old_switch_queue)
            ):
                at.remove_member(sched_switch)
                at.add_switch_command(
                    conf, "OFF" if i % 2 == 0 else "ON", sched_switch.dt
                )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c",
        "--configfile",
        nargs=1,
        default=None,
        help="Configration file path to amend.",
    )
    passed_args = parser.parse_args()

    do_setup(passed_args)
