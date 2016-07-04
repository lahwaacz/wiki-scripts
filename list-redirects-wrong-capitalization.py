#! /usr/bin/env python3

from ws.core import API
import ws.ArchWiki.lang as lang

# According to ArchWiki standards, the title must be sentence-case (if it is not
# an acronym) we will print the wrong capitalized redirects, i.e. when
# sentence-case title redirects to title-case.
def main(api):
    # limit to redirects pointing to the main namespace, others deserve special treatment
    redirects = api.site.redirects_map(source_namespaces=[0, 4, 12], target_namespaces=[0])

    # we will count the number of uppercase letters starting each word
    def count_uppercase(text):
        words = text.split()
        firstletters = [word[0] for word in words]
        return sum(1 for c in firstletters if c.isupper())

    for source in sorted(redirects.keys()):
        target = redirects[source].split("#", maxsplit=1)[0]

        # limit to redirects whose source and target title differ only in capitalization
        if source.lower() != target.lower():
            continue

        # limit to multiple-word titles
        pure, _ = lang.detect_language(source)
        if len(pure.split()) == 1:
            continue

        # limit to sentence-case titles redirecting to title-case
        if count_uppercase(source) >= count_uppercase(target):
            continue

        print("* [[{}]] --> [[{}]]".format(source, target))

if __name__ == "__main__":
    import ws.config
    api = ws.config.object_from_argparser(API, description="List redirect pages with wrong capitalization")
    main(api)
