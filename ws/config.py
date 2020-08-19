#! /usr/bin/env python3

import argparse
import configparser
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
CONFIG_DIR = os.path.expanduser("~/.config/")
CACHE_DIR = os.path.expanduser("~/.cache/")
DEFAULT_CONF = "default"


class ConfigParser(configparser.ConfigParser):
    """
    Drop-in replacement for :py:class:`configparser.Configparser`.
    """
    def __init__(self, configfile, **kwargs):
        kwargs.setdefault('interpolation', configparser.ExtendedInterpolation())
        super().__init__(**kwargs)
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
        # TODO: rewrite parsing of "multi-value" values
        for key, value in option_dict.items():
            if "," in value:
                option_dict[key] = [item.strip() for item in value.split(',')]
        if to_list:
            option_list = []
            for key, value in option_dict.items():
                option_list.append('--' + key)
                if isinstance(value, list):
                    option_list.extend(value)
                else:
                    option_list.append(value)
            
        return option_list if to_list else option_dict


class _ArgumentParser(argparse.ArgumentParser):
    """
    Drop-in replacement for :py:class:`argparse.ArgumentParser`.
    """
    def __init__(self, **kwargs):
        kwargs.setdefault("usage", "%(prog)s [options]")
        kwargs.setdefault("formatter_class", argparse.RawDescriptionHelpFormatter)
        super().__init__(**kwargs)

    def setup(self):
        """Initial argparser setup."""
        self.add_argument("-c", "--config", type=argtype_config, metavar="NAME", default=DEFAULT_CONF,
                help="name of config file (default: %(default)s)")
        self.add_argument("--cache-dir", type=argtype_dirname_must_exist, metavar="PATH",
                help=("directory for storing cached data (will be created if necessary, but parent directory must exist) (default: %(default)s)"))
        self.add_argument("--site", metavar="NAME",
                help="site name used in file naming schemes")
                          
        # some argument defaults that cannot be set with the "default=" parameter
        arg_defaults = {}
        cache_dir = os.getenv("XDG_CACHE_HOME", CACHE_DIR)
        arg_defaults["cache_dir"] = os.path.join(cache_dir, PROJECT_NAME)
        self.set_defaults(**arg_defaults)

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
    """Convert `--config` argument to an absolute file path."""
    dirname = os.path.dirname(string)
    name, ext = os.path.splitext(os.path.basename(string))

    # configuration name was specified
    if not dirname and ext != ".conf":
        config_dir = os.getenv("XDG_CONFIG_HOME", CONFIG_DIR)
        path = os.path.join(config_dir, "{}/{}.conf".format(PROJECT_NAME, string))
    # relative or absolute path was specified
    else:
        if ext != ".conf":
            raise argparse.ArgumentTypeError("config filename must end with '.conf' suffix: '%s'" % string)
        path = os.path.abspath(os.path.expanduser(string))

    if not os.path.exists(path):
        raise argparse.ArgumentTypeError("file does not exist or is a broken link: '%s'" % path)

    return path

# path to existing directory
def argtype_existing_dir(string):
    string = os.path.abspath(os.path.expanduser(string))
    if not os.path.isdir(string):
        raise configargparse.ArgumentTypeError("directory '%s' does not exist" % string)
    return string

# any path, the dirname part must exist (e.g. path to a file that will be created in the future)
def argtype_dirname_must_exist(string):
    string = os.path.abspath(os.path.expanduser(string))
    dirname, _ = os.path.split(string)
    if not os.path.isdir(dirname):
        raise configargparse.ArgumentTypeError("directory '%s' does not exist" % dirname)
    return string
        

def getArgParser(**kwargs):
    """
    Create an instance of :py:class:`_ArgumentParser`. Make its initial setup
    and set the logging arguments.

    :param kwargs: passed to :py:class:`_ArgumentParser()` constructor.
    :returns: an instance of :py:class:`_ArgumentParser`.
    """
    ap = _ArgumentParser(**kwargs)
    ap.setup()

    # include logging arguments into the global group
    ws.logging.set_argparser(ap)

    return ap


def object_from_argparser(klass, section=None, **kwargs):
    """
    Create an instance of ``klass`` using its :py:meth:`klass.from_argparser()`
    factory and a instance of :py:class:`_ArgumentParser`. On top of that, 
    logging interface is set up using the :py:mod:`ws.logging` module.

    :param klass: the class to instantiate
    :param str section:
        The name of the subsection to be read from the configuration file
        (usually the name of the script). By default ``sys.argv[0]`` is taken.
    :param kwargs: passed to :py:class:`_ArgumentParser()` constructor
    :returns: an instance of :py:class:`klass`
    """
    # argparser creation, initial setup and parsing sys.argv for config/cache-dir/etc options
    argparser = getArgParser(**kwargs)
    args, remaining_argv = argparser.parse_known_args()
    
    # read the config file and fetch the script-related section options
    cfp = ConfigParser(args.config)
    config_args = cfp.fetch_section(section)

    # class parser setup and final parsing
    klass.set_argparser(argparser)
    argparser.parse_known_args(config_args + remaining_argv, namespace=args)

    # set up logging
    ws.logging.init(args)
    logger.debug("Parsed arguments:\n{}".format(args))

    return klass.from_argparser(args)
