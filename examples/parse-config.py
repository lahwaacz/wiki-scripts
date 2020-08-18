#! /usr/bin/env python3

import ws.config

if __name__ == "__main__":
    argparser = ws.config.getArgParser(description="Simple example")

    argparser.add_argument("--foo",
                           help="foo option")
    argparser.add_argument("--files",
                           nargs="+",
                           type=ws.config.argtype_path,
                           action="check_dirname",
                           help="files option")

    args = argparser.parse_args()
    print(args)
