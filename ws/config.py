#! /usr/bin/env python3

import argparse
import configparser
import json
import logging
import os
import sys

import ws.logging

logger = logging.getLogger(__name__)

__all__ = [
    "ConfigParser",
    "argtype_bool",
    "argtype_config",
    "argtype_dirname_must_exist",
    "argtype_existing_dir",
    "getArgParser",
    "object_from_argparser",
]

PROJECT_NAME = "wiki-scripts"
CONFIG_DIR = os.getenv("XDG_CONFIG_HOME", os.path.expanduser("~/.config/"))
CONFIG_DIR = os.path.join(CONFIG_DIR, PROJECT_NAME)
CACHE_DIR = os.getenv("XDG_CACHE_HOME", os.path.expanduser("~/.cache/"))
CACHE_DIR = os.path.join(CACHE_DIR, PROJECT_NAME)
DEFAULT_CONF = "default"


class ConfigParser(configparser.ConfigParser):
    """
    Drop-in replacement for :py:class:`configparser.Configparser`.
    """
    def __init__(self, configfile, **kwargs):
        kwargs.setdefault("interpolation", configparser.ExtendedInterpolation())
        super().__init__(**kwargs)
        assert configfile is not None
        self.configfile = configfile

    def fetch_section(self, section=None, to_list=True):
        """
        Fetches a specific section from a config file.

        :param str section: section name for fetching.
        :param bool to_list: defines the format of the returned value (see below).
        :returns:
            The data from the fetched config file section. The format is
            a list of strings if ``to_list=True`` (default value) and
            a dictionary otherwise.
        """
        with open(self.configfile) as f:
            self.read_file(f)

        if section is None:
            section, _ = os.path.splitext(os.path.basename(sys.argv[0]))
        if not self.has_section(section):
            section = configparser.DEFAULTSECT

        option_dict = dict(self.items(section))
        for key, value in option_dict.items():
            value = value.strip()
            if value.startswith("["):
                option_dict[key] = [str(item) for item in json.loads(value)]
        if to_list is True:
            option_list = []
            for key, value in option_dict.items():
                option_list.append('--' + key)
                if isinstance(value, list):
                    option_list.extend(value)
                else:
                    option_list.append(value)
            return option_list
        return option_dict


# strict string to bool conversion
def argtype_bool(string):
    string = string.lower()
    true_values = {"yes", "true", "on", "1"}
    false_values = {"no", "false", "off", "0"}
    if string in true_values:
        return True
    elif string in false_values:
        return False
    else:
        raise argparse.ArgumentTypeError("value '{}' cannot be converted to boolean".format(string))

def argtype_config(string):
    """
    Compute config filepath and check its existence.
    """

    dirname = os.path.dirname(string)
    name, ext = os.path.splitext(os.path.basename(string))

    # configuration name was specified
    if not dirname and ext != ".conf":
        path = os.path.join(CONFIG_DIR, string + ".conf")
    # relative or absolute path was specified
    else:
        if ext != ".conf":
            raise argparse.ArgumentTypeError("config filename must end with '.conf' suffix: '{}'".format(string))
        path = os.path.abspath(os.path.expanduser(string))

    if not os.path.exists(path):
        if os.path.islink(path):
            raise argparse.ArgumentTypeError("symbolic link is broken: '{}'".format(path))
        elif string == DEFAULT_CONF:
            return None
        else:
            raise argparse.ArgumentTypeError("file does not exist: '{}'".format(path))
    return path

# path to existing directory
def argtype_existing_dir(string):
    string = os.path.abspath(os.path.expanduser(string))
    if not os.path.isdir(string):
        raise argparse.ArgumentTypeError("directory '{}' does not exist".format(string))
    return string

# any path, the dirname part must exist (e.g. path to a file that will be created in the future)
def argtype_dirname_must_exist(string):
    string = os.path.abspath(os.path.expanduser(string))
    dirname, _ = os.path.split(string)
    if not os.path.isdir(dirname):
        raise argparse.ArgumentTypeError("directory '{}' does not exist".format(dirname))
    return string


def getArgParser(**kwargs):
    """
    Create an instance of :py:class:`argparse.ArgumentParser`. Make its initial setup
    and set the logging arguments.

    :param kwargs: passed to :py:class:`argparse.ArgumentParser()` constructor.
    :returns: an instance of :py:class:`argparse.ArgumentParser`.
    """
    # parser for '--config' and '--no-config' options
    conf_ap = argparse.ArgumentParser(add_help=False)
    group = conf_ap.add_mutually_exclusive_group()
    group.add_argument("-c", "--config", type=argtype_config, metavar="PATH", default=DEFAULT_CONF,
            help="path to the config file; the shorthand name can be specified for files stored in {0} directory (default: {0}/{1}.conf)".format(CONFIG_DIR, DEFAULT_CONF))
    group.add_argument("--no-config", dest="config", const=None, action="store_const",
            help="run the script without parsing a config file")

    # main parser parameters
    kwargs.setdefault("usage", "%(prog)s [options]")
    kwargs.setdefault("formatter_class", argparse.RawDescriptionHelpFormatter)
    kwargs.setdefault("allow_abbrev", False)
    msg = ("\n\nArgs that start with '--' (e.g., --cache-dir) can also be set in a config file (specified via -c)."
           " If an arg is specified in more than one place, then commandline values override config file values"
           " which override defaults.")
    kwargs["description"] = kwargs.get("description", "") + msg
    kwargs["parents"] = kwargs.get("parents", []) + [conf_ap]

    # create the main parser and add global arguments
    ap = argparse.ArgumentParser(**kwargs)
    ap.add_argument("--cache-dir", type=argtype_dirname_must_exist, metavar="PATH", default=CACHE_DIR,
            help="directory for storing cached data (will be created if necessary, but parent directory must exist) (default: %(default)s)")

    # include logging arguments into the global group
    ws.logging.set_argparser(ap)

    return (ap, conf_ap)


def object_from_argparser(klass, section=None, **kwargs):
    """
    Create an instance of ``klass`` using its :py:meth:`klass.from_argparser()`
    factory and an instance of :py:class:`argparse.ArgumentParser`. On top of
    that, logging interface is set up using the :py:mod:`ws.logging` module.

    :param klass: the class to instantiate
    :param str section:
        The name of the subsection to be read from the configuration file
        (usually the name of the script). By default ``sys.argv[0]`` is taken.
    :param kwargs: passed to :py:class:`argparse.ArgumentParser()` constructor
    :returns: an instance of :py:class:`klass`
    """
    ap, conf_ap = getArgParser(**kwargs)
    klass.set_argparser(ap)

    cli_args = sys.argv[1:]
    config_args = []
    args = argparse.Namespace()

    conf_ap.parse_known_args(cli_args, namespace=args)

    # read the config file and fetch the script-related section
    if args.config is not None:
        cfp = ConfigParser(args.config)
        config_args += cfp.fetch_section(section)

    # parsing
    ap.parse_known_args(config_args + cli_args, namespace=args)

    # set up logging
    ws.logging.init(args)
    logger.debug("Parsed arguments:\n{}".format(args))

    return klass.from_argparser(args)
