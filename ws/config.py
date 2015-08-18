#! /usr/bin/env python3

import os
import sys
import collections
import logging

# TODO: make this an optional dependency, the from_argparser factory should work with plain argparse
import ConfigArgParse.configargparse as configargparse
import configfile
# allow '-' in config keys and section names
configfile.Section._OPTION = r'^[a-zA-Z_]+[a-zA-Z0-9_-]*$'
configfile.Section._SECTION_SUB = r'^[a-zA-Z_]+(?:\.?[a-zA-Z0-9_-]+)*$'
configfile.Section._SECTION_PLAIN = r'^[a-zA-Z_]+[a-zA-Z0-9_-]*$'

import ws.logging

logger = logging.getLogger(__name__)

__all__ = ["ConfigFileParser", "argtype_existing_dir", "argtype_dirname_must_exist", "getArgParser", "object_from_argparser"]

class ConfigFileParser:

    def __init__(self, top_level_arg, subname=None):
        self.top_level_arg = top_level_arg
        self.subname = subname

    def parse(self, stream, context=None):
        """
        Parses a config file and returns a dictionary of settings
        """
        # TODO: convert (all?) exceptions to configargparse.ConfigFileParserException
        cf = configfile.ConfigFile(stream, inherit_options=True, safe_calls=True, interpolation=True)

        try:
            _arg = "--" + self.top_level_arg
            _i = context.index(_arg)
            top_level = context[_i]
        except (ValueError, IndexError):
            top_level = None

        if top_level is None:
            top_level = cf[self.top_level_arg]
            if not top_level:
                raise coonfigargparse.ConfigFileParserException("top-level parameter '{}' not found")
        return cf(top_level, self.subname).get_options()

    def serialize(self, items):
        """
        Does the inverse of config parsing by taking parsed values and
        converting them back to a string representing config file contents.

        :param items: an ``OrderedDict`` with items to be written to the config file
        :returns: contents of config file as a string
        """
        raise NotImplementedError

    def get_syntax_description(self):
        return ""

class Defaults(collections.UserDict):
    def __init__(self):
        super().__init__()
        project_name = "wiki-scripts"

        # global arguments
        config_dir = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
        self.data["config"] = os.path.join(config_dir, "{0}/{0}.conf".format(project_name))

        cache_dir = os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache"))
        self.data["cache_dir"] = os.path.join(cache_dir, project_name)

        self.data["tmp_dir"] = os.path.join("/tmp", project_name)

        # ArchWiki specifics
        self.data["site"] = "ArchWiki"
        # NOTE: These depend on site=ArchWiki, but (config)argparse does not support conditional defaults
        # TODO: document the behaviour properly; also emphasize that --help does not
        #       take defaults from the config file (which is just right)
        self.data["api_url"] = "https://wiki.archlinux.org/api.php"
        self.data["index_url"] = "https://wiki.archlinux.org/index.php"

# any path, the dirname part must exist (e.g. path to a file that will be created in the future)
def argtype_dirname_must_exist(string):
    string = os.path.abspath(os.path.expanduser(string))
    dirname, _ = os.path.split(string)
    if not os.path.isdir(dirname):
        raise configargparse.ArgumentTypeError("directory '%s' does not exist" % dirname)
    return string

# path to existing directory
def argtype_existing_dir(string):
    string = os.path.abspath(os.path.expanduser(string))
    if not os.path.isdir(string):
        raise configargparse.ArgumentTypeError("directory '%s' does not exist" % string)
    return string

def getArgParser(subname=None, *args, **kwargs):
    if subname is None:
        _, _script = os.path.split(sys.argv[0])
        subname, _ = os.path.splitext(_script)

    # create config file parser
    cfp = ConfigFileParser("site", subname)
    kwargs["config_file_parser"] = cfp
    kwargs["ignore_unknown_config_file_keys"] = True

    # set brief usage parameter by default
    kwargs.setdefault("usage", "%(prog)s [options]")
    # TODO: the supplied description is merged with the one from configargparse, which looks very ugly

    ap = configargparse.ArgParser(*args, **kwargs)

    # add config file and site arguments
    ap.add_argument("-c", "--config", metavar="PATH", is_config_file_arg=True,
            help="path to config file (default: %(default)s)")
    ap.add_argument("--site",
            help="sets the top-level section to be read from config files (default: %(default)s)")

    # include logging arguments into the global group
    ws.logging.set_argparser(ap)

    # add other global arguments
    ap.add_argument("--tmp-dir", type=argtype_dirname_must_exist, metavar="PATH",
            help="temporary directory path (will be created if necessary, but parent directory must exist) (default: %(default)s)")
    ap.add_argument("--cache-dir", type=argtype_dirname_must_exist, metavar="PATH",
            help="directory for storing cached data (will be created if necessary, but parent directory must exist) (default: %(default)s)")

    ap.set_defaults(**Defaults())

    return ap

def object_from_argparser(klass, subname=None, *args, **kwargs):
    """
    Create an instance of ``klass`` using its :py:meth:`klass.from_argparser()`
    factory and a clean instance of :py:class:`argparse.ArgumentParser`. On top
    of that, logging interface is set up using the :py:mod:`ws.logging` module.

    :param klass: the class to instantiate
    :param subname:
        The name of the subsection to be read from the configuration file
        (usually the name of the script). By default ``sys.argv[0]`` is taken.
    :param args: passed to :py:class:`argparse.ArgumentParser()` constructor
    :param kwargs: passed to :py:class:`argparse.ArgumentParser()` constructor
    :returns: an instance of :py:class:`klass`
    """
    argparser = getArgParser(*args, **kwargs)
    klass.set_argparser(argparser)
    args = argparser.parse_args()

    # set up logging
    ws.logging.init(args)

    # TODO: depends on ConfigArgParse, in case of argparse just log the Namespace
    logger.debug("Parsed arguments:\n" + argparser.format_values())

    return klass.from_argparser(args)
