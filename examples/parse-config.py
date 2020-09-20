#! /usr/bin/env python3

import ws.config

if __name__ == "__main__":
    argparser, _ = ws.config.getArgParser(description="Simple example")

    argparser.add_argument("--foo", help="foo option")

    args = argparser.parse_args()
    print(args)
