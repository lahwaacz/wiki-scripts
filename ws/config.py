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
    "getArgParser", 
    "object_from_argparser",
    "argtype_bool",
    "argtype_configfile",
    "argtype_path",
]

PROJECT_NAME = 'wiki-scripts'
CONFIG_DIR = '~/.config/'       # Can be overriden by XDG_CONFIG_HOME
CACHE_DIR = '~/.cache/'         # Can be overriden by XDG_CACHE_HOME
DEFAULT_CONF = 'default'        # Can be overriden with '--config' option


# ==============
# Parser classes
# ==============

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

        option_dict = dict(self.items(section))
        for key, value in option_dict.items():
            if ' ' in value:
                option_dict[key] = value.split()
        if to_list:
            option_list = []
            for key, value in option_dict.items():
                option_list.append(key)
                if isinstance(value, list):
                    option_list.extend(value)
                else:
                    option_list.append(value)
            
        return option_list if to_list else option_dict


class _ArgumentParser(argparse.ArgumentParser):
    """Drop-in replacement for :py:class:`argparse.ArgumentParser`."""

    def __init__(self, **kwargs):
        kwargs.setdefault('usage', '%(prog)s [options]')
        kwargs.setdefault('formatter_class',
                          argparse.RawDescriptionHelpFormatter)
        super().__init__(**kwargs)
        # register new actions
        self.register('action', 'check_path', _ActionCheckPath)
        self.register('action', 'check_dirname', _ActionCheckDirname)

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
                          
        # some argument defaults that cannot be set with the 'default='
        # parameter
        arg_defaults = {}

        cache_dir = os.getenv('XDG_CACHE_HOME', os.path.expanduser(CACHE_HOME))
        arg_defaults['cache_dir'] = os.path.join(cache_dir, PROJECT_NAME)
        
        self.set_defaults(**arg_defaults)


# =======================
# Type conversion methods
# =======================

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
            "cannot convert '{}'to boolean".format(string))


def argtype_configfile(string):
    """Convert `--config` argument to an absolute file path."""
    dirname = os.path.dirname(string)
    name, ext = os.path.splitext(os.path.basename(string))

    # Configuration name was specified.
    if not dirname and not ext:
        config_dir = os.getenv('XDG_CONFIG_HOME',
                               os.path.expanduser(CONFIG_DIR))
        path = os.path.join(config_dir,
                            "{}/{}.conf".format(PROJECT_NAME, string))
    # Relational or absolute path was specified.
    elif:
        if ext != '.conf':
            raise argparse.ArgumentTypeError(
                "config filename must end with '.conf' suffix")
        path = os.path.abspath(os.path.expanduser(string))

    return path
        
def argtype_path(string):
    """Convert a string to an absolute filesystem path."""
    return os.path.abspath(os.path.expanduser(string))


# ==============
# Action classes
# ==============

class _ActionCheckPath(argparse.Action):

    def __call__(self, parser, namespace, path, option_string=None):
        if not os.path.lexists(path)
            raise FileNotFoundError(
                "no such file or directory: {}".format(path)
        setattr(namespace, self.dest, path)
    

class _ActionCheckDirname(argparse.Action):

    def __call__(self, parser, namespace, path, option_string=None):
        dirname = os.path.dirname(path)
        if not os.path.isdir(dirname)
            raise FileNotFoundError(
                "no such directory: {}".format(dirname))
        setattr(namespace, self.dest, path)


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
    :param section:
        The name of the subsection to be read from the configuration file
        (usually the name of the script). By default ``sys.argv[0]`` is taken.
    :param kwargs: passed to :py:class:`_ArgumentParser()` constructor
    :returns: an instance of :py:class:`klass`
    """

    # argparser creation, initial setup and parsing sys.argv
    # for config/cache-dir/etc options
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
