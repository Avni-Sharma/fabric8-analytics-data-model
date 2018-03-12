"""Tests for the data_importer module (to be done)."""

import data_importer
import pytest


def test_parse_int_or_none_for_integer_input():
    """Test the function parse_int_or_none() for integer inputs."""
    assert 0 == data_importer.parse_int_or_none(0)
    assert 1 == data_importer.parse_int_or_none(1)
    assert -1 == data_importer.parse_int_or_none(-1)


def test_parse_int_or_none_for_float_input():
    """Test the function parse_int_or_none() for float inputs."""
    assert 0 == data_importer.parse_int_or_none(0.0)
    assert 1 == data_importer.parse_int_or_none(1.0)
    assert 1 == data_importer.parse_int_or_none(1.1)
    assert 1 == data_importer.parse_int_or_none(1.9)
    assert -1 == data_importer.parse_int_or_none(-1)


def test_parse_int_or_none_for_string_input():
    """Test the function parse_int_or_none() for string input."""
    assert 42 == data_importer.parse_int_or_none("42")
    assert 42 == data_importer.parse_int_or_none("42.1")
    assert 41 == data_importer.parse_int_or_none("41.9")
    assert -42 == data_importer.parse_int_or_none("-42")
    assert -42 == data_importer.parse_int_or_none("-42.1")
    assert -41 == data_importer.parse_int_or_none("-41.9")


def test_parse_int_or_none_for_unicode_string_input():
    """Test the function parse_int_or_none() for Unicode string input."""
    assert 42 == data_importer.parse_int_or_none(u"42")
    assert 42 == data_importer.parse_int_or_none(u"42.1")
    assert 41 == data_importer.parse_int_or_none(u"41.9")
    assert -42 == data_importer.parse_int_or_none(u"-42")
    assert -42 == data_importer.parse_int_or_none(u"-42.1")
    assert -41 == data_importer.parse_int_or_none(u"-41.9")


def test_parse_int_or_none_for_invalid_input():
    """Test the function parse_int_or_none() for invalid input."""
    assert data_importer.parse_int_or_none(None) is None
    assert data_importer.parse_int_or_none(True) == 1
    assert data_importer.parse_int_or_none(False) == 0
    assert data_importer.parse_int_or_none([]) is None
    assert data_importer.parse_int_or_none({}) is None


if __name__ == '__main__':
    test_parse_int_or_none_for_integer_input()
    test_parse_int_or_none_for_float_input()
    test_parse_int_or_none_for_string_input()
    test_parse_int_or_none_for_unicode_string_input()
    test_parse_int_or_none_for_invalid_input()
