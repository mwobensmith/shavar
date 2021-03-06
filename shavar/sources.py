import os
# posixpath instead of os.path because posixpath will always use / as the path
# separator.  Basically a Windows portability consideration.
import posixpath
import tempfile
import time
from urlparse import urlparse

from boto.s3.connection import S3Connection

from shavar.exceptions import NoDataError, ParseError
from shavar.parse import parse_file_source


class Source(object):
    """
    Base class for data sources
    """

    def __init__(self, source_url, refresh_interval):
        self.source_url = source_url
        self.url = urlparse(self.source_url)
        self.interval = refresh_interval
        self.last_refresh = 0
        self.last_check = 0
        self.chunks = None
        self.chunk_index = None
        self.prefixes = None

    def load(self):
        raise NotImplemented

    def _populate_chunks(self, fp, parser_func):
        try:
            self.chunks = parser_func(fp)
            self.last_check = int(time.time())
            self.last_refresh = int(time.time())
            self.chunk_index = {'adds': set(self.chunks.adds.keys()),
                                'subs': set(self.chunks.subs.keys())}
        except ParseError, e:
            raise ParseError('Error parsing "%s": %s' % (self.url.path, e))

    def refresh(self):
        # Prevent constant refresh checks
        now = int(time.time())
        if now - self.interval >= self.last_check:
            self.last_check = now
            if self.needs_refresh():
                self.load()
                return True
        return False

    def needs_refresh(self):
        return False

    def fetch(self, adds, subs):
        self.refresh()

        chunks = {'adds': [], 'subs': []}
        for chunk_num in adds:
            chunks['adds'].append(self.chunks.adds[chunk_num])
        for chunk_num in subs:
            chunks['subs'].append(self.chunks.subs[chunk_num])
        return chunks

    def list_chunks(self):
        self.refresh()
        return (self.chunk_index['adds'], self.chunk_index['subs'])

    def find_prefix(self, prefix):
        return self.chunks.find_prefix(prefix)


# FIXME  Some of the logic here probably needs to be migrated into the Source
#        class
class FileSource(Source):
    """
    Source for single files accessible via simple filesystem calls
    """

    def load(self):
        if not os.path.exists(self.url.path):
            # We can't find the data for that list
            raise NoDataError('Known list, no data found: "%s"'
                              % self.url.path)

        with open(self.url.path, 'rb') as f:
            self._populate_chunks(f, parse_file_source)

    def needs_refresh(self):
        if int(os.stat(self.url.path).st_mtime) <= self.last_refresh:
            return False
        return True


class S3FileSource(Source):
    """
    Loads chunks from a single file in S3 in the on-the-wire format
    """

    def __init__(self, source_url, refresh_interval):
        super(S3FileSource, self).__init__(source_url, refresh_interval)
        self.current_etag = None
        # eliminate preceding slashes in the S3 key name
        elems = list(posixpath.split(posixpath.normpath(self.url.path)))
        while '/' == elems[0]:
            elems.pop(0)
        self.key_name = posixpath.join(*elems)

    def _get_key(self):
        bucket = S3Connection().get_bucket(self.url.netloc)
        return bucket.get_key(self.key_name)

    def load(self):
        s3key = self._get_key()
        if not s3key:
            raise NoDataError('No chunk file found at "%s"' % self.source_url)

        with tempfile.TemporaryFile() as fp:
            s3key.get_contents_to_file(fp)
            # Need to forcibly reset to the beginning of the file
            fp.seek(0)
            self._populate_chunks(fp, parse_file_source)
            self.current_etag = s3key.etag

    def needs_refresh(self):
        s3key = self._get_key()
        if s3key.etag == self.current_etag:
            return False
        return True
