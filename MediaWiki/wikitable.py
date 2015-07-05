#! /usr/bin/env python3

import re

class Wikitable:
    @staticmethod
    def assemble(header_fields, rows):
        """
        :param header_fields: list of strings representing the table header
        :param rows: list of tuples, represents the table cells in a matrix-like
                     row-major format
        :returns: string containing the table formatted with MediaWiki markup
        """
        header = '{{| class="wikitable sortable" border=1\n' + \
                 "! {}\n" * len(header_fields)
        rowtemplate = "|-\n" + "| {}\n" * len(header_fields)

        text = header.format(*header_fields)
        for row in rows:
            text += rowtemplate.format(*row)
        text += "|}\n"
        
        return text

    # TODO: this is not general at all, it is able to parse only the table
    #       produced by Wikitable.assemble()
    @staticmethod
    def parse(text):
        """
        :param text: string or a :py:class:`mwparserfromhell.wikicode.Wikicode`
                     object containing a table in MediaWiki format
        :returns: list of tuples representing the table cells in a matrix-like
                  row-major format
        """
        rowre = re.compile("^\|\-(.*?)(?=(\|\-|\|\}))", flags=re.MULTILINE | re.DOTALL)
        cellre = re.compile("^\|\s*(.*?)$", flags=re.MULTILINE)

        rows = []
        for row in re.finditer(rowre, str(text)):
            cells = re.findall(cellre, row.group(1))
            rows.append(tuple(cells))

        if len(rows) == 0:
            raise WikitableParseError

        return rows

class WikitableParseError(Exception):
    pass
