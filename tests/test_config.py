#!/usr/bin/env python3

from argparse import ArgumentTypeError
import os
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


class test__get_config_filepath:
    """Tests for '_get_config_filepath()' function."""

    @pytest.mark.parametrize("string", ["default", "archwiki", "wiki.archlinux.org", "hello-world.py"])
    def test_configuration_name(self, string):
        path = ws.config._get_config_filepath(string)
        config_dir = os.getenv("XDG_CONFIG_HOME", ws.config.CONFIG_DIR)
        result = os.path.join(config_dir, "{}/{}.conf".format(ws.config.PROJECT_NAME, string))
        assert path == result

    @pytest.mark.parametrize("string", ["./hello", "~/hello.world", "/home/username/.config/config"])
    def test_path_with_slashes_but_without_conf_suffix(self, string):
        with pytest.raises(ArgumentTypeError) as excinfo:
            path = ws.config._get_config_filepath(string)
        msg = "config filename must end with '.conf' suffix" 
        assert msg in str(excinfo.value)

    @pytest.mark.parametrize("string", ["./hello.conf", "~/hello.world.conf", "/home/.config/config.conf"])
    def test_path_with_slashes_and_conf_suffix(self, string):
        path = ws.config._get_config_filepath(string)
        result = os.path.abspath(os.path.expanduser(string))
        assert path == result


class test_argtype_config:

    def test_existing_file(self, tmp_path):
        config = tmp_path / "archwiki.conf"
        config.touch()
        path = ws.config.argtype_config(config)
        assert path == str(config)

    def test_nonexisting_file(self, tmp_path):
        config = tmp_path / "helloworld.conf"
        with pytest.raises(ArgumentTypeError) as excinfo:
            path = ws.config.argtype_config(config)
        msg = "file does not exist or is a broken link" 
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
        msg = "file does not exist or is a broken link" 
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