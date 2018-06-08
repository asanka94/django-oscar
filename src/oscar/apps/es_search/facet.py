from collections import OrderedDict
from purl import URL

from django.utils.translation import gettext_lazy as _


class Facet(object):

    facet_name = None

    def __init__(self, name, agg, request_url, user_defined_facets, selected_facets={}):
        self.field_name = name
        self.agg = agg
        self.user_defined_facets = user_defined_facets
        self.selected_facets = selected_facets
        self.base_url = URL(request_url)
        if 'buckets' in agg:
            self.buckets = agg['buckets']
            # If not, the subclass needs to find the right buckets...

    def get_field_value(self, bucket):
        return str(bucket['key'])

    def get_display_name(self, bucket):
        return self.get_field_value(bucket)

    def get_select_url(self, field_value):
        """
        :param field_value: Value of the bucket field
        :return: A url that adds a filter for this value
        """
        url = self.base_url.append_query_param(
            'selected_facets', '%s:%s' % (self.field_name, field_value))
        return self.strip_pagination(url)

    def get_deselect_url(self, field_value):
        """
        :param field_value: Value of the bucket field
        :return: A url that removes the filter for this value
        """
        url = self.base_url.remove_query_param(
            'selected_facets', '%s:%s' % (self.field_name, field_value))
        return self.strip_pagination(url)

    @staticmethod
    def strip_pagination(url):
        if url.has_query_param('page'):
            url = url.remove_query_param('page')
        return url.as_string()

    def build_facet_result(self, bucket):
        field_value = self.get_field_value(bucket)
        facet = {
            'name': self.get_display_name(bucket),
            'count': bucket['doc_count'],
            'show_count': True,
            'selected': False,
            'disabled': (int(bucket['doc_count']) == 0)
        }
        if field_value in self.selected_facets.get(self.field_name, []):
            # This filter is selected - build the 'deselect' URL
            facet['selected'] = True
            facet['deselect_url'] = self.get_deselect_url(field_value)
        else:
            facet['select_url'] = self.get_select_url(field_value)

        return facet

    def get_facet_display_name(self):
        """
        :return: The title used when displaying this facet
        """
        label = self.field_name.capitalize()
        if self.user_defined_facets.get(self.field_name, {}).get('label'):
            label = self.user_defined_facets[self.field_name]['label']

        return label

    def get_facet(self):
        return {
            'name': self.get_facet_display_name(),
            'results': [self.build_facet_result(bucket) for bucket in self.buckets]
        }


class RangeFacet(Facet):

    """
    NOTE: Elasticsearch's range aggregations are bit awkward because
    they exclude the "to" value from the range. There is jiggery pokery here
    to alter the display value of the upper bound.

    Currently this code assumes integer ranges only.
    """

    @staticmethod
    def get_field_value(bucket):
        from_value = bucket.get('from', '')
        to_value = bucket.get('to', '')
        return '{}-{}'.format(from_value, to_value)

    @staticmethod
    def get_display_name(bucket):
        from_value = int(bucket.get('from', 0))
        to_value = int(bucket.get('to', 0))
        if not from_value:
            return _('Up to {}'.format(to_value))
        if not to_value:
            return _('{} and above'.format(from_value))
        return _('{} to {}'.format(from_value, to_value))

    def get_facet(self):
        # skip if all the `doc_count` values are zero
        if not any(b['doc_count'] for b in self.buckets):
            return {
                'name': self.get_facet_display_name(),
                'results': []
            }

        return super().get_facet()


class HistogramFacet(Facet):

    def get_display_name(self, bucket):
        interval = self.user_defined_facets[self.field_name]['params']['interval']

        from_value = int(float(bucket.get('key')))

        to_display_value = (from_value + interval) - 1

        if not from_value:
            return 'Up to {}'.format(to_display_value)
        return '{} to {}'.format(from_value, to_display_value)


class FacetsBuilder(object):

    FACET_TYPE_MAPPING = {
        'range': RangeFacet,
        'auto_range': RangeFacet,
        'histogram': HistogramFacet
    }

    def __init__(self, aggs, request_url, selected_facets={}, user_defined_facets={}):
        self.aggs = aggs
        self.request_url = request_url
        self.selected_facets = selected_facets
        self.user_defined_facets = user_defined_facets

    def get_facet_class(self, facet_type):
        return self.FACET_TYPE_MAPPING.get(facet_type, Facet)

    def sort_facets(self, facets):
        # Sort facets based on the order of facets defined in settings
        sorted_facets = []
        for field in self.user_defined_facets.keys():
            if field in facets:
                sorted_facets.append((field, facets.pop(field)))

        # If anything is left, leave it at the end
        for field in list(facets):
            sorted_facets.append((field, facets.pop(field)))

        return sorted_facets

    def build_facets(self):
        facets = {}
        for field, agg in self.aggs.items():
            if not isinstance(agg, dict):
                continue

            facet_type = self.user_defined_facets.get(field, {})['type']
            FacetClass = self.get_facet_class(facet_type)

            facets[field] = FacetClass(
                name=field,
                agg=agg,
                request_url=self.request_url,
                selected_facets=self.selected_facets,
                user_defined_facets=self.user_defined_facets).get_facet()

        facets = self.sort_facets(facets)

        return OrderedDict(facets)
