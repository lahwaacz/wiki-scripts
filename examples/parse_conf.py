#!/usr/bin/env python3

import argparse
import configparser

# Parse the config file
parser = configparser.ConfigParser()
parser.read('config.ini')
topsecret_conf = dict(parser['topsecret'])
print("\n[DEFAULT] section parameters:")
print(dict(parser['DEFAULT']))
print("\n[topsecret] section parameters."
      " [DEFAULT]s included, but forwardx11 is overriden:")
print(topsecret_conf)

# Parse the command-line arguments.
argparser = argparse.ArgumentParser()
argparser.add_argument('--port')
argparser.add_argument('-f', '--forwardx11')
args = argparser.parse_args(['--forwardx11', 'true', '--port', '499'])
# Transform Namespace object to dict.
args = vars(args)

print("\nOnly the command-line args:")
print(args)

# Merge two dicts.
conf = {**topsecret_conf, **args}

print("\nBoth conf file and cli args."
      " port is overriden, and forwardx11 is overriden too (again):")
print(conf)

# Wrap arguments into the Namespase object.
conf = argparse.Namespace(**conf)

print("\nCommon Namespace object:")
print(conf)
print("\nAccess to individual arguments:")
print("conf.port is '{}'".format(conf.port))
print("conf.forwardx11 is '{}'".format(conf.forwardx11))
