#! /usr/bin/env python3

import argparse
import configparser
import logging
import os
import sys

import ws.logging

logger = logging.getLogger(__name__)

__all__ = [
    'ConfigParser', 
    'getArgParser', 
    'object_from_argparser',
    'argtype_configfile',
    'argtype_existing_dir', 
    'argtype_dirname_must_exist', 
]

PROJECT_NAME = 'wiki-scripts'
CONFIG_DIR = '~/.config/'       # Can be overriden by XDG_CONFIG_HOME
CACHE_DIR = '~/.cache/'         # Can be overriden by XDG_CACHE_HOME
DEFAULT_CONF = 'archwiki'       # Can be overriden with '--config' option

class ConfigParser(configparser.ConfigParser):
    """Drop-in replacement for :py:class:`configparser.Configparser`."""

    def __init__(self, configfile):
        super().__init__()
        self.configfile = configfile

    def fetch_section(self, section=None, to_list=True):
        """
        Fetches a specific section from a config file.

        :param section: section name for fetching.
        :param to_list: defines the format of the returned value (see below).
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

        data = self.items(section)
        return [f'--{k}={v}' for k, v in data] if to_list else dict(data)


class ArgumentParser(argparse.ArgumentParser):
    """Drop-in replacement for :py:class:`argparse.ArgumentParser`."""

    def __init__(self, **kwargs):
        kwargs.setdefault('usage', '%(prog)s [options]')
        kwargs.setdefault('formatter_class',
                          argparse.RawDescriptionHelpFormatter)
        super().__init__(**kwargs)

    def setup(self):
        """Initial argparser setup."""
        
        self.add_argument('-c', '--config',
                          type=argtype_configfile,
                          metavar='NAME',
                          default=DEFAULT_CONF,
                          help='name of config file (default: %(default)s')
        self.add_argument('--cache-dir',
                          type=argtype_dirname_must_exist,
                          metavar='PATH',
                          help=('directory for storing cached data'
                                ' (will be created if necessary,'
                                ' but parent directory must exist)'
                                ' (default: %(default)s')
                          
        # Some argument defaults that cannot be set with the 'default='
        # parameter
        arg_defaults = {}

        cache_dir = os.getenv('XDG_CACHE_HOME', os.path.expanduser(CACHE_HOME))
        arg_defaults['cache_dir'] = os.path.join(cache_dir, PROJECT_NAME)
        
        self.set_defaults(**arg_defaults)


def argtype_configfile(string):
    """Convert `--config` argument to the full config file path. Check file
    existance.

    :param string: configuration name.
    :returns: the config file path.
    """
    confdir = os.getenv('XDG_CONFIG_HOME', os.path.expanduser(CONFIG_DIR))
    config = os.path.join(confdir, '{}/{}.conf'.format(PROJECT_NAME, string))
    if not os.path.isfile(config):
        raise FileNotFoundError(
            'No such configuration file: "{}"'.format(config))
    else:
        return config
        

def argtype_bool(string):
    """
    Convert the string represenation of a bool value to the true
    :py:class:`bool` instance.

    :returns: ``True`` or ``False``.
    """
    string = string.lower()
    true_values = {'yes', 'true', 'on', '1'}
    false_values = {'no', 'false', 'off', '0'}
    if string in true_values:
        return True
    elif string in false_values:
        return False
    else:
        raise argparse.ArgumentTypeError(
            'string "{}" cannot be converted to a bool.'.format(sting))

# any path, the dirname part must exist (e.g. path to a file that will be created in the future)
def argtype_dirname_must_exist(string):
    string = os.path.abspath(os.path.expanduser(string))
    dirname, _ = os.path.split(string)
    if not os.path.isdir(dirname):
        raise argparse.ArgumentTypeError("directory '%s' does not exist" % dirname)
    return string

# path to existing directory
def argtype_existing_dir(string):
    string = os.path.abspath(os.path.expanduser(string))
    if not os.path.isdir(string):
        raise argparse.ArgumentTypeError("directory '%s' does not exist" % string)
    return string

# list of comma-separated items from a fixed set
def argtype_comma_list_choices(choices):
    choices = set(choices)

    def wrapped(string):
        items = [item.strip() for item in string.split(",")]
        for item in items:
            if item not in choices:
                raise argparse.ArgumentTypeError("unknown item: '{}' (available choices: {})".format(item, choices))
        return items

    return wrapped


def getArgParser(**kwargs):
    """
    Create an instance of :py:class:`ArgumentParser`. Make its initial setup
    and set the logging arguments.

    :param kwargs: passed to :py:class:`ArgumentParser()` constructor.
    :returns: an instance of :py:class:`ArgumentParser`.
    """
    ap = ArgumentParser(**kwargs)
    ap.setup()

    # include logging arguments into the global group
    ws.logging.set_argparser(ap)

    return ap


def object_from_argparser(klass, section=None, **kwargs):
    """
    Create an instance of ``klass`` using its :py:meth:`klass.from_argparser()`
    factory and a instance of :py:class:`ArgumentParser`. On top of that, 
    logging interface is set up using the :py:mod:`ws.logging` module.

    :param klass: the class to instantiate
    :param section:
        The name of the subsection to be read from the configuration file
        (usually the name of the script). By default ``sys.argv[0]`` is taken.
    :param kwargs: passed to :py:class:`ArgumentParser()` constructor
    :returns: an instance of :py:class:`klass`
    """

    # argparser creation, initial setup and parsing sys.argv
    # for config/site/etc options
    argparser = getArgParser(**kwargs)
    argparser.setup()
    args, remaining_argv = argparser.parse_known_args()
    
    # read the config file and fetch the script-related section options
    cfp = ConfigParser(args.config)
    config_args = cfp.fetch_section(section)
    
    # class parser setup and final parsing
    klass.set_argparser(argparser)
    argparser.parse_args(config_args + remaining_argv, namespace=args)

    # set up logging
    ws.logging.init(args)
    logger.debug("Parsed arguments:\n" + argparser.format_values())

    return klass.from_argparser(args)
