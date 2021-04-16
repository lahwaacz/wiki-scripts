## Rules

These rules are taken from [HTTPS Everywhere](https://github.com/EFForg/https-everywhere) which is licensed under GPL v2+.

To update the rule sets:

    git clone https://github.com/EFForg/https-everywhere.git
    cd https-everywhere
    python utils/merge-rulesets.py

Then copy `rules/default.rulesets.json` into this repository.

## Code

Likewise, the code in this submodule is based on the [HTTPS Everywhere Rule Checker](
https://github.com/EFForg/https-everywhere/blob/master/test/rules/README.md).
Adjustments were made as needed (e.g. to read rulesets from JSON rather than XML).
