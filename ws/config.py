#! /usr/bin/env python3

import argparse
import collections
import configparser
import logging
import os
import sys

import ws.logging

logging = logger.getLogger(__name__)

__all__ = [
    "ConfigFileParser", 
    "argtype_existing_dir", 
    "argtype_dirname_must_exist", 
    "getArgParser", 
    "object_from_argparser",
]

class ConfigFileParser:

    def __init__(self, subname=None):
        self.subname = subname

    def parse(self, configfile):
        """Parse a config file and return a dict of options."""
        cf = configparser.ConfigParser()
        cf.read(configfile)
        return dict(cf[self.subname])

    def parse_to_list(self, configfile):
        """Parse a config file and return the options
        as the list of strings.
        """
        cf = self.parse(configfile)
        conv = []
        for option, value in cf.items():
            conv.append('--' + option)
            conf.append(value)
        return conv


class Defaults(collections.UserDict):
    def __init__(self):
        super().__init__()
        project_name = "wiki-scripts"

        # global arguments
        config_dir = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
        self.data["config"] = os.path.join(config_dir, "{0}/{0}.conf".format(project_name))

        cache_dir = os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache"))
        self.data["cache_dir"] = os.path.join(cache_dir, project_name)

        # ArchWiki specifics
        self.data["site"] = "ArchWiki"
        # NOTE: These depend on site=ArchWiki, but (config)argparse does not support conditional defaults
        # TODO: document the behaviour properly; also emphasize that --help does not
        #       take defaults from the config file (which is just right)
        self.data["api_url"] = "https://wiki.archlinux.org/api.php"
        self.data["index_url"] = "https://wiki.archlinux.org/index.php"

def argtype_bool(value):
    if isinstance(value, bool):
        return value
    string = str(value).lower()
    if string in ["1", "true", "yes"]:
        return True
    elif string in ["0", "false", "no"]:
        return False
    else:
        print("value '%s' cannot be converted to boolean" % value)
        raise argparse.ArgumentTypeError("value '%s' cannot be converted to boolean" % value)

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

def getArgParser(subname=None, **kwargs):
    if subname is None:
        _, _script = os.path.split(sys.argv[0])
        subname, _ = os.path.splittext(_script)

    # set brief usage parameter by default
    kwargs.setdefault("usage", "%(prog)s [options]")
    kwargs.setdefault("formatter_class", argparse.RawDescriptionHelpFormatter)

    ap = argparse.ArgumentParser(**kwargs)

    # add config file argument
    ap.add_argument("-c", "--config", metavar="PATH",
            help="path to config file (default: %(default)s)")

    # include logging arguments into the global group
    ws.logging.set_argparser(ap)

    # add other global arguments
    ap.add_argument("--cache-dir", type=argtype_dirname_must_exist, metavar="PATH",
            help="directory for storing cached data (will be created if necessary, but parent directory must exist) (default: %(default)s)")

    ap.set_defaults(**Defaults())

    return ap

def object_from_argparser(klass, subname=None, **kwargs):
    """
    Create an instance of ``klass`` using its :py:meth:`klass.from_argparser()`
    factory and a clean instance of :py:class:`argparse.ArgumentParser`. On top
    of that, logging interface is set up using the :py:mod:`ws.logging` module.

    :param klass: the class to instantiate
    :param subname:
        The name of the subsection to be read from the configuration file
        (usually the name of the script). By default ``sys.argv[0]`` is taken.
    :param kwargs: passed to :py:class:`argparse.ArgumentParser()` constructor
    :returns: an instance of :py:class:`klass`
    """
    if subname is None:
        _, _script = os.path.split(sys.argv[0])
        subname, _ = os.path.splittext(_script)
    argparser = getArgParser(subname, **kwargs)
    args, remaining_argv = argparser.parse_known_args()
    klass.set_argparser(argparser)
    cfp = ConfigFileParser(subname)
    config_args = cfp.parse_to_list(args.config)
    argparser.parse_args(config_args, namespace=args)
    argparser.parse_args(remaining_argv, namespace=args)

    # set up logging
    ws.logging.init(args)

    # TODO: depends on ConfigArgParse, in case of argparse just log the Namespace
    logger.debug("Parsed arguments:\n" + argparser.format_values())

    return klass.from_argparser(args)
