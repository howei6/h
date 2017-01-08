# -*- coding: utf-8 -*-
import logging
from collections import namedtuple

from memex.search import query

FILTERS_KEY = 'memex.search.filters'
MATCHERS_KEY = 'memex.search.matchers'

log = logging.getLogger(__name__)


annotation_ids_map = {}

SearchResult = namedtuple('SearchResult', [
    'total',
    'annotation_ids',
    'annotation_ids_map',
    'reply_ids',
    'aggregations'])




class Search(object):
    """
    Search is the primary way to initiate a search on the annotation index.

    :param request: the request object
    :type request: pyramid.request.Request

    :param separate_replies: Wheter or not to return all replies to the
        annotations returned by this search. If this is True then the
        resulting annotations will only include top-leve annotations, not replies.
    :type separate_replies: bool
    """
    def __init__(self, request, separate_replies=False):
        self.request = request
        self.es = request.es
        self.separate_replies = separate_replies

        self.builder = default_querybuilder(request)
        self.reply_builder = default_querybuilder(request)

    def run(self, params):
        """
        Execute the search query

        :param params: the search parameters
        :type params: dict-like

        :returns: The search results
        :rtype: SearchResult
        """
        total, annotation_ids, annotation_ids_map, aggregations = self.search_annotations(params)
        reply_ids = self.search_replies(annotation_ids)

        return SearchResult(total, annotation_ids, annotation_ids_map, reply_ids, aggregations)

    def append_filter(self, filter_):
        """Append a search filter to the annotation and reply query."""
        self.builder.append_filter(filter_)
        self.reply_builder.append_filter(filter_)

    def append_matcher(self, matcher):
        """Append a search matcher to the annotation and reply query."""
        self.builder.append_matcher(matcher)
        self.reply_builder.append_matcher(matcher)

    def append_aggregation(self, aggregation):
        self.builder.append_aggregation(aggregation)

    def search_annotations(self, params):
        if self.separate_replies:
            self.builder.append_filter(query.TopLevelAnnotationsFilter())
        
        print params
        response = self.es.conn.search(index=self.es.index,
                                       doc_type=self.es.t.annotation,
                                       _source=False,
                                       body=self.builder.build(params))
        print response
        total = response['hits']['total']
        annotation_ids = [hit['_id'] for hit in response['hits']['hits']]
        for itemvar in response['hits']['hits']:
            annotation_ids_map[itemvar['_id']] = itemvar['_score']
        aggregations = self._parse_aggregation_results(response.get('aggregations', None))
        return (total, annotation_ids, annotation_ids_map, aggregations)

    def search_replies(self, annotation_ids):
        if not self.separate_replies:
            return []

        self.reply_builder.append_matcher(query.RepliesMatcher(annotation_ids))
        response = self.es.conn.search(index=self.es.index,
                                       doc_type=self.es.t.annotation,
                                       _source=False,
                                       body=self.reply_builder.build({'limit': 200}))

        if len(response['hits']['hits']) < response['hits']['total']:
            log.warn("The number of reply annotations exceeded the page size "
                     "of the Elasticsearch query. We currently don't handle "
                     "this, our search API doesn't support pagination of the "
                     "reply set.")

        return [hit['_id'] for hit in response['hits']['hits']]

    def _parse_aggregation_results(self, aggregations):
        if not aggregations:
            return {}

        results = {}
        for key, result in aggregations.iteritems():
            for agg in self.builder.aggregations:
                if key != agg.key:
                    continue

                results[key] = agg.parse_result(result)
                break

        return results


def default_querybuilder(request):
    builder = query.Builder()
    builder.append_filter(query.AuthFilter(request))
    builder.append_filter(query.UriFilter(request))
    builder.append_filter(query.GroupFilter())
    builder.append_filter(query.UserFilter())
    builder.append_matcher(query.AnyMatcher())
    builder.append_matcher(query.TagsMatcher())
    for factory in request.registry.get(FILTERS_KEY, []):
        builder.append_filter(factory(request))
    for factory in request.registry.get(MATCHERS_KEY, []):
        builder.append_matcher(factory(request))
    return builder
