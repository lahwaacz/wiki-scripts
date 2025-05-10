#! /usr/bin/env python3

# TODO:
# - use the SQL database, it is enough to export the data as files to the directory tree

import datetime
import hashlib
import os

import ws.ArchWiki.lang
from ws.client import API
from ws.utils import list_chunks


class Downloader:
    extension = "mediawiki"

    def __init__(self, api, output_directory, epoch, safe_filenames):
        self.api = api
        self.output_directory = output_directory
        self.epoch = epoch
        self.safe_filenames = safe_filenames

        # ensure output directory always exists
        if not os.path.isdir(self.output_directory):
            os.mkdir(self.output_directory)

        # list of valid files
        self.files = []

    def get_local_filename(self, title, basepath):
        """
        Return file name where the given page should be stored, relative to `basepath`.
        """
        title, lang = ws.ArchWiki.lang.detect_language(title)
        _title = self.api.Title(title)

        # be safe and use '_' instead of ' ' in filenames (MediaWiki style)
        title = _title.pagename.replace(" ", "_")
        namespace = _title.namespace.replace(" ", "_")

        # force ASCII filename
        if self.safe_filenames and not title.isascii():
            h = hashlib.md5()
            h.update(title.encode("utf-8"))
            title = h.hexdigest()

        # select pattern per namespace
        if namespace == "":
            pattern = "{base}/{langsubtag}/{title}.{ext}"
        elif namespace in ["Talk", "ArchWiki", "ArchWiki_talk", "Template", "Template_talk", "Help", "Help_talk", "Category", "Category_talk"]:
            pattern = "{base}/{langsubtag}/{namespace}:{title}.{ext}"
        elif namespace == "File":
            pattern = "{base}/{namespace}:{title}"
        else:
            pattern = "{base}/{namespace}:{title}.{ext}"

        path = pattern.format(
            base=basepath,
            langsubtag=ws.ArchWiki.lang.tag_for_langname(lang),
            namespace=namespace,
            title=title,
            ext=self.extension
        )
        return os.path.normpath(path)

    def needs_update(self, fname, timestamp):
        """
        Determine if it is necessary to download a page.
        """
        if not os.path.exists(fname):
            return True
        local = datetime.datetime.utcfromtimestamp(os.path.getmtime(fname))
        if local < timestamp or local < self.epoch:
            return True
        return False

    def process_namespace(self, namespace):
        """
        Enumerate all pages in given namespace, download if necessary
        """
        print("Processing namespace %s..." % namespace)
        allpages = api.generator(generator="allpages", gaplimit="max", gapfilterredir="nonredirects", gapnamespace=namespace, prop="info")

        to_be_updated = []
        for page in allpages:
            title = page["title"]
            fname = self.get_local_filename(title, self.output_directory)
            self.files.append(fname)
            timestamp = page["touched"]
            if self.needs_update(fname, timestamp):
                print("  [new rev found] %s" % title)
                to_be_updated.append( (title, page["pageid"], fname) )
            else:
                print("  [up to date]    %s" % title)

        # sort by title (first item in tuple)
        to_be_updated.sort()

        for snippet in list_chunks(to_be_updated, api.max_ids_per_query):
            # unzip the list of tuples
            titles, pageids, fnames = zip(*snippet)
            print("  [downloading]   '{}' ... '{}'".format(titles[0], titles[-1]))
            result = api.call_api(action="query", pageids="|".join(str(pid) for pid in pageids), prop="revisions", rvprop="content", rvslots="main")

            for page in result["pages"].values():
                pageid = page["pageid"]
                fname = fnames[pageids.index(pageid)]
                text = page["revisions"][0]["slots"]["main"]["*"]

                # ensure that target directory exists (necessary for subpages)
                try:
                    os.makedirs(os.path.split(fname)[0])
                except FileExistsError:
                    pass

                f = open(fname, "w")
                f.write(text)
                f.close()

    def clean_output_directory(self):
        """
        Walk output_directory and delete all files not found on the wiki.
        Should be run _after_ downloading, otherwise all files will be deleted!
        """
        print("Deleting unwanted files (deleted/moved on the wiki)...")
        valid_files = self.files.copy()

        for path, dirs, files in os.walk(self.output_directory, topdown=False):
            # handle files
            for f in files:
                fpath = os.path.join(path, f)
                if fpath not in valid_files:
                    print("  [deleting]    %s" % fpath)
                    os.unlink(fpath)

            # remove empty directories
            if len(os.listdir(path)) == 0:
                print("  [deleting]    %s/" % path)
                os.rmdir(path)


if __name__ == "__main__":
    import ws.config

    argparser = ws.config.getArgParser(description="Clone latest revisions of pages on the wiki")
    API.set_argparser(argparser)

    # TODO: move to Dowloader.set_argparser()
    _script = argparser.add_argument_group(title="script parameters")
    _script.add_argument("--output-directory", metavar="PATH", required=True, type=ws.config.argtype_existing_dir,
            help="Output directory path, will be created if needed.")
    _script.add_argument("--force", action="store_true",
            help="Ignore timestamp, always download the latest revision from the wiki.")
    _script.add_argument("--clone-talks", action="store_true",
            help="Also clone talk namespaces.")
    _script.add_argument("--clean", action="store_true",
            help="Clean the output directory after cloning, useful for removing pages deleted/moved on the wiki. Warning: any unknown files found in the output directory will be deleted!")
    _script.add_argument("--safe-filenames", action="store_true",
            help="Force using ASCII file names instead of the default Unicode.")

    args = ws.config.parse_args(argparser)

    api = API.from_argparser(args)

    # TODO: simplify for Downloader.from_argparser()
    if args.force:
        epoch = datetime.datetime.now(datetime.UTC)
    else:
        # this should be the date of the latest incompatible change
        epoch = datetime.datetime(2015, 5, 1, tzinfo=datetime.UTC)

    downloader = Downloader(api, args.output_directory, epoch, args.safe_filenames)

    namespaces = ["0", "4", "10", "12", "14"]
    if args.clone_talks:
        namespaces += ["1", "5", "11", "13", "15"]

    for ns in namespaces:
        downloader.process_namespace(ns)

    if args.clean:
        downloader.clean_output_directory()
