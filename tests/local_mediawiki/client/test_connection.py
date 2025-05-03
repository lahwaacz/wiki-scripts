import pytest

import ws.client.connection
from ws.client.connection import APIError, APIExpandResultFailed, APIWrongAction


class test_connection:
    """
    Tests :py:class:`ws.client.connection` methods on :py:obj:`api` fixture.

    TODO:
        - cookies
        - set_argparser, from_argparser
        - call_index
    """

    def test_coverage(self, mediawiki):
        api = mediawiki.api
        paraminfo = api.call_api(action="paraminfo", modules="main")
        actions = set(paraminfo["modules"][0]["parameters"][0]["type"])
        assert actions == ws.client.connection.API_ACTIONS

    # check correct server
    def test_url(self, mediawiki):
        api = mediawiki.api
        assert api.api_url == f"{mediawiki.url}/api.php"

    def test_params_is_dict(self, mediawiki):
        api = mediawiki.api
        with pytest.raises(ValueError):
            api.call_api(params=("foo", "bar"))

    def test_wrong_action(self, mediawiki):
        api = mediawiki.api
        with pytest.raises(APIWrongAction):
            api.call_api(params={"action": "wrong action"})

    def test_empty_query_expand(self, mediawiki):
        api = mediawiki.api
        with pytest.raises(APIExpandResultFailed):
            api.call_api(action="query")

    def test_empty_query(self, mediawiki):
        api = mediawiki.api
        expected_response = {"batchcomplete": ""}
        assert api.call_api(action="query", expand_result=False) == expected_response

    def test_post_action(self, mediawiki):
        api = mediawiki.api
        with pytest.raises(APIError):
            api.call_api(action="stashedit")

    def test_help(self, mediawiki):
        api = mediawiki.api
        h = api.call_api(action="help")
        assert h["mime"] == "text/html"
        assert isinstance(h["help"], str)

    def test_mixed_params_and_kwargs(self, mediawiki):
        api = mediawiki.api
        with pytest.raises(ValueError):
            api.call_api(params={"meta": "siteinfo"}, action="query")
