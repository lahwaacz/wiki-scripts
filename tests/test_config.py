#!/usr/bin/env python3

import sys
from argparse import ArgumentTypeError

import pytest

import ws.config


class test_argtype_bool:
    """Tests for 'argtype_bool()' function."""

    @pytest.mark.parametrize("string", ["yes", "on", "true", "1", "Yes", "TruE", "ON"])
    def test_true(self, string):
        result = ws.config.argtype_bool(string)
        assert result == True

    @pytest.mark.parametrize("string", ["no", "off", "false", "0", "No", "FalSE", "OFF"])
    def test_false(self, string):
        result = ws.config.argtype_bool(string)
        assert result == False

    def test_cannot_be_converted(self):
        string = "hello"
        msg = "cannot be converted to boolean"
        with pytest.raises(ArgumentTypeError) as excinfo:
            result = ws.config.argtype_bool(string)
        assert msg in str(excinfo.value)

    @pytest.mark.parametrize("string", [True, 4, 5.5, ["hello", "world"]])
    def test_not_str_passed(self, string):
        msg = "object has no attribute 'lower'"
        with pytest.raises(AttributeError) as excinfo:
            result = ws.config.argtype_bool(string)
        assert msg in str(excinfo.value)


class test_argtype_config:

    @pytest.mark.parametrize("string", [ws.config.DEFAULT_CONF, "archwiki", "wiki.archlinux.org", "hello-world.py"])
    def test_configuration_name(self, tmp_path, monkeypatch, string):
        monkeypatch.setattr(ws.config, "CONFIG_DIR", tmp_path)
        config = tmp_path / (string + ".conf")
        config.touch()
        path = ws.config.argtype_config(string)
        assert path == str(config)

    def test_default_fallback(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ws.config, "CONFIG_DIR", tmp_path)
        path = ws.config.argtype_config(ws.config.DEFAULT_CONF)
        assert path is None

    @pytest.mark.parametrize("string", [ws.config.DEFAULT_CONF, "archwiki", "wiki.archlinux.org", "hello-world.py"])
    def test_path_with_slashes_but_without_conf_suffix(self, tmp_path, string):
        config = tmp_path / string
        with pytest.raises(ArgumentTypeError) as excinfo:
            path = ws.config.argtype_config(config)
        msg = "config filename must end with '.conf' suffix"
        assert msg in str(excinfo.value)

    def test_existing_file(self, tmp_path):
        config = tmp_path / "archwiki.conf"
        config.touch()
        path = ws.config.argtype_config(config)
        assert path == str(config)

    def test_nonexisting_file(self, tmp_path):
        config = tmp_path / "helloworld.conf"
        with pytest.raises(ArgumentTypeError) as excinfo:
            path = ws.config.argtype_config(config)
        msg = "file does not exist"
        assert msg in str(excinfo.value)

    def test_symbolic_link(self, tmp_path):
        config = tmp_path / "default.conf"
        dummy_file = tmp_path / "config.conf"
        dummy_file.touch()
        config.symlink_to(dummy_file)
        path = ws.config.argtype_config(config)
        assert path == str(config)

    def test_broken_link(self, tmp_path):
        config = tmp_path / "broken-default.conf"
        dummy_file = tmp_path / "not-exist.conf"
        config.symlink_to(dummy_file)
        with pytest.raises(ArgumentTypeError) as excinfo:
            path = ws.config.argtype_config(config)
        msg = "symbolic link is broken"
        assert msg in str(excinfo.value)


class test_argtype_existing_dir:
    """Tests for 'argtype_existing_dir()' funtion."""

    def test_exising_dir(self, tmp_path):
        directory = tmp_path / "existing-dir"
        directory.mkdir()
        path = ws.config.argtype_existing_dir(directory)
        assert path == str(directory)

    def test_nonexising_dir(self, tmp_path):
        directory = tmp_path / "non-existing-dir"
        with pytest.raises(ArgumentTypeError) as excinfo:
            path = ws.config.argtype_existing_dir(directory)
        msg = "directory '%s' does not exist" % directory
        assert msg == str(excinfo.value)


class test_argtype_dirname_must_exist:
    """Tests for 'argtype_dirname_must_exist()' function."""

    def test_filepath_with_existing_dirname(self, tmp_path):
        existing_dir = tmp_path / "subdir"
        existing_dir.mkdir()
        existing_file = existing_dir / "file.txt"
        existing_file.touch()
        path = ws.config.argtype_dirname_must_exist(existing_file)
        assert path == str(existing_file)

    def test_filepath_with_nonexisting_dirname(self, tmp_path):
        existing_file = tmp_path / "subdir" / "not-a-file.txt"
        with pytest.raises(ArgumentTypeError) as excinfo:
            path = ws.config.argtype_dirname_must_exist(existing_file)
        msg = "directory '%s' does not exist" % existing_file.parent
        assert msg == str(excinfo.value)


@pytest.fixture
def cfp(tmp_path):
    data = """
    [DEFAULT]
    default_opt1 = value1
    default_opt2 =  value2

    [section1]
    sec1_opt1 = value3
    sec1_opt2 = value4

    [section2]
    multi-value = [
        "config.py",
        "hello-world.conf",
        "/file/path/with spaces,and, commas"
        ]

    [section3]
    a = spam
    """
    configfile = tmp_path / "config.conf"
    with open(configfile, "w") as f:
        f.write(data)
    return ws.config.ConfigParser(configfile)

class test_fetch_section:
    """Tests for 'ConfigParser.fetch_section()' method."""

    def test_existent_section(self, cfp):
        values = cfp.fetch_section(section="section1")
        result = ["--default_opt1", "value1", "--default_opt2", "value2",
                  "--sec1_opt1", "value3", "--sec1_opt2", "value4"]
        assert values == result

    def test_section_not_specified(self, cfp):
        values = cfp.fetch_section()
        result = ["--default_opt1", "value1", "--default_opt2", "value2"]
        assert values == result

    def test_multiline_value(self, cfp):
        values = cfp.fetch_section(section="section2")
        result = ["--default_opt1", "value1", "--default_opt2", "value2",
                  "--multi-value", "config.py", "hello-world.conf", "/file/path/with spaces,and, commas"]
        assert values == result

    def test_to_dict(self, cfp):
        values = cfp.fetch_section(to_list=False)
        result = {"default_opt1": "value1", "default_opt2": "value2"}
        assert values == result

    def test_short_option_in_config_file(self, cfp):
        with pytest.raises(ArgumentTypeError) as excinfo:
            values = cfp.fetch_section(section="section3")
        msg = "short options are not allowed in a config file: 'a'"
        assert msg == str(excinfo.value)

class obj_simple:
    def __init__(self, foo, bar):
        self.foo = foo
        self.bar = bar

    @staticmethod
    def set_argparser(argparser):
        argparser.add_argument("--foo", required=True, choices=["a", "b"])
        argparser.add_argument("--bar", default="baz")

    @classmethod
    def from_argparser(klass, args):
        return klass(args.foo, args.bar)

class test_object_from_argparser:
    """Tests for the :py:func:`ws.config.object_from_argparser` function."""

    def test_undefined(self, capsys):
        with pytest.raises(SystemExit) as excinfo:
            ws.config.object_from_argparser(obj_simple)
        assert excinfo.type == SystemExit
        assert excinfo.value.code == 2
        assert "error: the following arguments are required: --foo" in capsys.readouterr().err

    def test_defined_on_cli(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["prog", "--foo", "a"])
        obj = ws.config.object_from_argparser(obj_simple)
        assert obj.foo == "a"

    def test_defined_in_config(self, monkeypatch, tmp_path):
        config = tmp_path / "default.conf"
        with open(config, "w") as f:
            f.write("[DEFAULT]\nfoo = a\n")
        monkeypatch.setattr(sys, "argv", ["prog", "--config", str(config)])
        obj = ws.config.object_from_argparser(obj_simple)
        assert obj.foo == "a"

    def test_defined_in_both(self, monkeypatch, tmp_path):
        config = tmp_path / "default.conf"
        with open(config, "w") as f:
            f.write("[DEFAULT]\nfoo = a\n")
        monkeypatch.setattr(sys, "argv", ["prog", "--foo", "b", "--config", str(config)])
        obj = ws.config.object_from_argparser(obj_simple)
        assert obj.foo == "b"

    def test_unknown_config_argument(self, monkeypatch, tmp_path):
        config = tmp_path / "default.conf"
        with open(config, "w") as f:
            f.write("[DEFAULT]\nunknown = value\n")
        monkeypatch.setattr(sys, "argv", ["prog", "--foo", "a", "--config", str(config)])
        obj = ws.config.object_from_argparser(obj_simple)
        assert obj.foo == "a"

    def test_long_unknown_command_line_argument(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", ["prog", "--foo", "a", "--unknown", "value"])
        with pytest.raises(SystemExit) as excinfo:
            obj = ws.config.object_from_argparser(obj_simple)
        assert excinfo.type == SystemExit
        assert excinfo.value.code == 2
        assert "error: unrecognized arguments: --unknown" in capsys.readouterr().err

    def test_short_unknown_command_line_argument(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", ["prog", "--foo", "a", "-u", "value"])
        with pytest.raises(SystemExit) as excinfo:
            obj = ws.config.object_from_argparser(obj_simple)
        assert excinfo.type == SystemExit
        assert excinfo.value.code == 2
        assert "error: unrecognized arguments: -u" in capsys.readouterr().err

    def test_multiple_unknown_command_line_argument(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", ["prog", "--foo", "a", "--unknown", "-u", "value"])
        with pytest.raises(SystemExit) as excinfo:
            obj = ws.config.object_from_argparser(obj_simple)
        assert excinfo.type == SystemExit
        assert excinfo.value.code == 2
        assert "error: unrecognized arguments: --unknown -u" in capsys.readouterr().err

    def test_multiple_unknown_short_options_in_cli(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", ["prog", "--foo", "b", "-abc"])
        with pytest.raises(SystemExit) as excinfo:
            obj = ws.config.object_from_argparser(obj_simple)
        assert excinfo.type == SystemExit
        assert excinfo.value.code == 2
        assert "error: unrecognized arguments: -abc" in capsys.readouterr().err


    def test_no_config(self, monkeypatch, tmp_path):
        monkeypatch.setattr(ws.config, "CONFIG_DIR", tmp_path)
        config = tmp_path / "default.conf"
        with open(config, "w") as f:
            f.write("[DEFAULT]\nfoo = a\nbar = c\n")
        monkeypatch.setattr(sys, "argv", ["prog", "--foo", "b", "--no-config"])
        obj = ws.config.object_from_argparser(obj_simple)
        assert obj.bar == "baz"

    def test_no_config_side_by_side_with_config(self, monkeypatch, tmp_path, capsys):
        config = tmp_path / "default.conf"
        with open(config, "w") as f:
            f.write("[DEFAULT]\nfoo = a\nbar = c\n")
        monkeypatch.setattr(sys, "argv", ["prog", "--foo", "b", "--no-config", "--config", str(config)])
        with pytest.raises(SystemExit) as excinfo:
            obj = ws.config.object_from_argparser(obj_simple)
        assert excinfo.type == SystemExit
        assert excinfo.value.code == 2
        assert "error: argument -c/--config: not allowed with argument --no-config" in capsys.readouterr().err
